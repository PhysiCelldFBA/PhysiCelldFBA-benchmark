#ifndef PHYSICELL_BENCHMARK_RUNTIME_H
#define PHYSICELL_BENCHMARK_RUNTIME_H
#include "telemetry.h"
#include "../../core/PhysiCell.h"
#include "../../modules/PhysiCell_standard_modules.h"
#ifdef ADDON_PHYSIDFBA
#include "../../addons/dFBA/src/dfba_intracellular.h"
#endif
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <limits>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>

namespace PCBenchmark {
using namespace PhysiCell;
using namespace BioFVM;
inline pugi::xml_node options() { return physicell_config_root.child("benchmark"); }
inline std::string quote(const std::string& s) {
    std::string out = "\"";
    for (char c : s) { if (c == '\\' || c == '"') out += '\\'; if (c == '\n') out += "\\n"; else out += c; }
    return out + "\"";
}
struct Observation {
    std::ofstream cells, fluxes, substrates, population, ledger;
    std::vector<double> before_amount, expected_delta;
    bool net_export_only = true;
    std::map<int, std::vector<double>> initial_positions;
    std::map<int, double> initial_volumes;
    std::map<std::string, double> density;
    std::vector<int> order;
    std::set<std::string> issues;
    unsigned initial_cells = 0, max_occupancy = 0;
    double min_concentration = std::numeric_limits<double>::infinity();
};
inline Observation& observation() { static Observation o; return o; }
inline double dry_mass_pg(Cell* c) {
    double density = observation().density.at(c->type_name);
#ifdef ADDON_PHYSIDFBA
    auto* m = dynamic_cast<PhysiCelldFBA::dFBAIntracellular*>(c->phenotype.intracellular);
    if (m) density = m->cell_density;
#endif
    return c->phenotype.volume.total * (1-c->phenotype.volume.fluid_fraction) * density;
}
inline void initialize() {
    auto node = options();
    if (!node.attribute("enabled").as_bool(false)) throw std::runtime_error("Benchmark executable requires <benchmark enabled=\"true\">");
    state().threads.resize(omp_get_max_threads());
    state().enabled = true;
    state().fixed_population = node.attribute("fixed_population").as_bool(false);
    state().fixed_volume = node.attribute("fixed_volume").as_bool(false);
    state().diagnostics = node.attribute("diagnostics").as_bool(false);
    if (state().fixed_volume && !state().fixed_population) throw std::runtime_error("Fixed volume requires fixed population");
    for (auto n : node.children("cell_type")) observation().density[n.attribute("name").value()] = n.attribute("density_g_ml").as_double();
    for (auto& p : observation().density) if (!(p.second > 0)) throw std::runtime_error("Positive cell dry-mass density required");
    #pragma omp parallel
    {
        #pragma omp single
        count("actual_threads", omp_get_num_threads());
    }
}
inline void create_controlled_cells() {
    const std::string layout = options().attribute("layout").value();
    int n = options().attribute("cells").as_int();
    if (n < 1) throw std::runtime_error("Positive benchmark cell count required");
    if (layout != "lattice" && layout != "single" && layout != "shared" && layout != "explicit") throw std::runtime_error("Unknown controlled layout");
    std::vector<std::vector<double>> prescribed;
    if (layout == "explicit") {
        for (auto node : options().children("cell_position")) {
            std::vector<double> p;
            for (auto axis : {"x", "y", "z"}) {
                if (!node.attribute(axis)) throw std::runtime_error("Missing cell coordinate");
                p.push_back(node.attribute(axis).as_double());
            }
            for (int a=0; a<3; ++a)
                if (!std::isfinite(p[a]) || p[a]<=microenvironment.mesh.bounding_box[a] || p[a]>=microenvironment.mesh.bounding_box[a+3])
                    throw std::runtime_error("Cell coordinate outside domain");
            if (std::find(prescribed.begin(),prescribed.end(),p)!=prescribed.end()) throw std::runtime_error("Duplicate cell center");
            prescribed.push_back(p);
        }
        if (int(prescribed.size())!=n) throw std::runtime_error("Explicit position count mismatch");
    }
    if (layout == "lattice" && n > int(microenvironment.number_of_voxels())) throw std::runtime_error("Not enough distinct voxels");
    for (int i=0; i<n; ++i) {
        // Mixed case alternates definitions without changing their physiology.
        auto* definition = cell_definitions_by_index[options().attribute("mixed").as_bool(false) ? i % cell_definitions_by_index.size() : 0];
        Cell* c = create_cell(*definition);
        std::vector<double> pos(3,0);
        for (int axis=0; axis<3; ++axis) pos[axis]=0.5*(microenvironment.mesh.bounding_box[axis]+microenvironment.mesh.bounding_box[axis+3]);
        pos=microenvironment.nearest_voxel(pos).center;
        auto position=options().child("position");
        if (position) for(int axis=0;axis<3;++axis) pos[axis]=position.attribute(std::string(1,"xyz"[axis]).c_str()).as_double();
        if (layout == "lattice") pos = microenvironment.voxels(i).center;
        if (layout == "explicit") pos = prescribed[i];
        c->assign_position(pos);
    }
}
inline void configure_cells() {
    auto& o = observation();
    o.initial_cells = all_cells->size();
    for (Cell* c : *all_cells) {
        if (!o.density.count(c->type_name)) throw std::runtime_error("Missing benchmark cell_type density for " + c->type_name);
        if (options().attribute("fixed_positions").as_bool(false)) c->is_movable = false;
        if (state().fixed_volume) c->functions.volume_update_function = nullptr;
        if (!c->phenotype.intracellular) {
            c->functions.pre_update_intracellular = nullptr;
            c->functions.post_update_intracellular = nullptr;
        }
        if (state().fixed_population) {
            c->functions.cell_division_function = nullptr;
            std::fill(c->phenotype.death.rates.begin(), c->phenotype.death.rates.end(), 0.0);
        }
        o.initial_positions[c->ID] = c->position;
        o.initial_volumes[c->ID] = c->phenotype.volume.total;
    }
    // Explicit Fisher-Yates with mt19937 and rejection sampling: independent
    // from PhysiCell's RNG and stable across standard-library shuffle variants.
    if (options().attribute("permute").as_bool(false)) {
        std::mt19937 rng(options().attribute("order_seed").as_uint());
        for (unsigned n=all_cells->size(); n>1; --n) {
            const unsigned threshold = unsigned(-n) % n;
            unsigned r; do { r = rng(); } while (r < threshold);
            std::swap((*all_cells)[n-1], (*all_cells)[r % n]);
        }
        for (unsigned i=0; i<all_cells->size(); ++i) (*all_cells)[i]->index = i;
    }
    std::ofstream order("benchmark_order.csv"); order << "traversal_index,cell_id\n";
    for (unsigned i=0; i<all_cells->size(); ++i) { o.order.push_back((*all_cells)[i]->ID); order << i << ',' << (*all_cells)[i]->ID << '\n'; }
    std::ofstream positions("benchmark_positions.csv");
    positions << "cell_id,x_um,y_um,z_um,voxel_index\n" << std::setprecision(17);
    for (Cell* c : *all_cells) positions << c->ID << ',' << c->position[0] << ',' << c->position[1] << ',' << c->position[2] << ',' << c->get_current_voxel_index() << '\n';
    // Only synthetic extra fields receive this documented spatial initial state.
    for (unsigned f=0; f<microenvironment.number_of_densities(); ++f)
        if (microenvironment.density_names[f].find("benchmark_extra_") == 0)
            for (unsigned v=0; v<microenvironment.number_of_voxels(); ++v)
                microenvironment.density_vector(v)[f] = 1.0 + 0.1*std::sin(microenvironment.voxels(v).center[0]);
    if (state().diagnostics) {
        o.cells.open("benchmark_cells.csv"); o.cells << "time_minutes,cell_id,dry_mass_pg,volume_um3,growth_per_hour,primary_status,secondary_status,total_internal_abs_flux\n";
        o.fluxes.open("benchmark_fluxes.csv"); o.fluxes << "time_minutes,cell_id,field_index,net_export_BioFVM_per_min\n";
        o.substrates.open("benchmark_substrates.csv"); o.substrates << "time_minutes,phase,field_index,field_name,amount_concentration_um3,min_concentration\n";
        o.population.open("benchmark_population.csv"); o.population << "time_minutes,phase,cells,total_dry_mass_pg,max_cells_per_voxel\n";
        o.ledger.open("benchmark_exchange_balance.csv"); o.ledger << "time_minutes,field_index,before_amount,after_amount,expected_net_export_delta,observed_delta,residual,net_export_only\n";
    }
}
inline void after_update(void* raw) {
    if (!state().diagnostics) return;
    auto* c = static_cast<Cell*>(raw);
    std::ostringstream row; row << std::setprecision(17) << PhysiCell_globals.current_time << ',' << c->ID << ',' << dry_mass_pg(c) << ',' << c->phenotype.volume.total;
#ifdef ADDON_PHYSIDFBA
    auto* m = dynamic_cast<PhysiCelldFBA::dFBAIntracellular*>(c->phenotype.intracellular);
    auto sol = m->sbml_model.getSolution();
    row << ',' << m->get_growth_rate() << ',' << sol.status << ',' << sol.secondary_status << ',' << m->sbml_model.getTotalAbsoluteFlux();
#else
    row << ",0,none,none,0";
#endif
    local().cell_rows.push_back(row.str());
    for (unsigned f=0; f<c->phenotype.secretion.net_export_rates.size(); ++f) {
        std::ostringstream flux; flux << std::setprecision(17) << PhysiCell_globals.current_time << ',' << c->ID << ',' << f << ',' << c->phenotype.secretion.net_export_rates[f];
        local().flux_rows.push_back(flux.str());
    }
}
inline void observe(const char* phase) {
    Timer timer("validation_seconds");
    auto& o = observation();
    double biomass = 0; std::map<int,unsigned> occupancy;
    for (Cell* c : *all_cells) {
        biomass += dry_mass_pg(c); ++occupancy[c->get_current_voxel_index()];
        if (!std::isfinite(dry_mass_pg(c))) o.issues.insert("nonfinite_biomass");
        if (state().fixed_population && (c->phenotype.death.dead || !o.initial_volumes.count(c->ID))) o.issues.insert("population_changed");
        if (options().attribute("fixed_positions").as_bool(false) && c->position != o.initial_positions[c->ID]) o.issues.insert("position_changed");
        if (state().fixed_volume && std::abs(c->phenotype.volume.total-o.initial_volumes[c->ID]) > 1e-10*std::max(1.0,o.initial_volumes[c->ID])) o.issues.insert("volume_changed");
#ifdef ADDON_PHYSIDFBA
        auto* m = dynamic_cast<PhysiCelldFBA::dFBAIntracellular*>(c->phenotype.intracellular);
        if (m && !c->phenotype.death.dead && PhysiCell_globals.current_time-m->next_dfba_run > 0.00010001) o.issues.insert("overdue_intracellular_update");
#endif
    }
    unsigned maximum=0; for (auto p : occupancy) maximum=std::max(maximum,p.second);
    o.max_occupancy = std::max(o.max_occupancy, maximum);
    if (options().attribute("expected_max_occupancy") && maximum!=options().attribute("expected_max_occupancy").as_uint())
        o.issues.insert("unexpected_voxel_occupancy");
    if (state().fixed_population && all_cells->size()!=o.initial_cells) o.issues.insert("population_changed");
    if (options().attribute("layout").as_string()==std::string("lattice") && maximum>1) o.issues.insert("shared_voxel_in_scaling_case");
    if (state().diagnostics) o.population << std::setprecision(17) << PhysiCell_globals.current_time << ',' << phase << ',' << all_cells->size() << ',' << biomass << ',' << maximum << '\n';
    for (unsigned f=0; f<microenvironment.number_of_densities(); ++f) {
        double total=0, minimum=std::numeric_limits<double>::infinity();
        for (unsigned v=0; v<microenvironment.number_of_voxels(); ++v) {
            double value=microenvironment.density_vector(v)[f];
            if (!std::isfinite(value)) o.issues.insert("nonfinite_concentration");
            minimum=std::min(minimum,value); total+=value*microenvironment.voxels(v).volume;
        }
        o.min_concentration=std::min(o.min_concentration,minimum);
        if (minimum<0) o.issues.insert("negative_concentration");
        if (state().diagnostics) o.substrates << std::setprecision(17) << PhysiCell_globals.current_time << ',' << phase << ',' << f << ',' << microenvironment.density_names[f] << ',' << total << ',' << minimum << '\n';
    }
}
inline void before_exchange(double dt) {
    if (!state().diagnostics) return;
    Timer timer("validation_seconds");
    auto& o=observation();
    unsigned fields=microenvironment.number_of_densities();
    o.before_amount.assign(fields,0); o.expected_delta.assign(fields,0); o.net_export_only=true;
    for(unsigned v=0;v<microenvironment.number_of_voxels();++v)
        for(unsigned f=0;f<fields;++f) o.before_amount[f]+=microenvironment.density_vector(v)[f]*microenvironment.voxels(v).volume;
    for(Cell* c:*all_cells) if(!c->is_out_of_domain && c->is_active)
        for(unsigned f=0;f<fields;++f) {
            o.expected_delta[f]+=c->phenotype.secretion.net_export_rates[f]*dt;
            if(c->phenotype.secretion.secretion_rates[f]!=0 || c->phenotype.secretion.uptake_rates[f]!=0) o.net_export_only=false;
        }
}
inline void exchange_observation() {
    if (!state().diagnostics) return;
    observe("after_exchange_before_fba");
    Timer timer("validation_seconds"); auto& o=observation();
    for(unsigned f=0;f<microenvironment.number_of_densities();++f) {
        double after=0;
        for(unsigned v=0;v<microenvironment.number_of_voxels();++v) after+=microenvironment.density_vector(v)[f]*microenvironment.voxels(v).volume;
        double delta=after-o.before_amount[f];
        o.ledger << std::setprecision(17) << PhysiCell_globals.current_time << ',' << f << ',' << o.before_amount[f] << ',' << after << ',' << o.expected_delta[f] << ',' << delta << ',' << delta-o.expected_delta[f] << ',' << o.net_export_only << '\n';
    }
}
inline void flush_rows() {
    Timer timer("output_seconds");
    for (auto& thread : state().threads) {
        for (auto& row : thread.cell_rows) observation().cells << row << '\n';
        for (auto& row : thread.flux_rows) observation().fluxes << row << '\n';
        thread.cell_rows.clear(); thread.flux_rows.clear();
    }
}
inline void finish(const std::string& exception = "") {
    auto& o=observation();
    std::map<std::string,double> totals;
    std::map<int,unsigned long long> expected, actual;
    for (auto& t:state().threads) {
        for(auto p:t.values) {
            if(p.first.size()>4 && p.first.substr(p.first.size()-4)=="_max") totals[p.first]=std::max(totals[p.first],p.second);
            else totals[p.first]+=p.second;
        }
        for(auto p:t.due) expected[p.first]+=p.second;
        for(auto p:t.updated) actual[p.first]+=p.second;
    }
    if(expected!=actual) o.issues.insert("due_actual_update_mismatch");
    if(totals["solver_failures"]>0) o.issues.insert("primary_solver_failure");
    if(totals["stage_two_failures"]>0) o.issues.insert("pfba_fallback");
    if(!exception.empty()) o.issues.insert("exception");
    std::ofstream updates("benchmark_update_counts.csv"); updates << "cell_id,due,actual\n";
    for(auto p:actual) expected.emplace(p.first,0);
    for(auto p:expected) updates << p.first << ',' << p.second << ',' << actual[p.first] << '\n';
    totals["initial_cells"]=o.initial_cells; totals["final_cells"]=all_cells->size();
    totals["max_cells_per_voxel"]=o.max_occupancy; totals["voxel_count"]=microenvironment.number_of_voxels();
    totals["solver_thread_seconds"]=totals["stage_one_thread_seconds"]+totals["stage_two_thread_seconds"];
    const char* zero_keys[]={"optimization_calls","initial_solve_calls","model_optimization_calls","stage_one_solve_calls","stage_two_solve_calls","stage_two_retries","intracellular_updates"};
    for(auto key:zero_keys) totals.emplace(key,0);
    std::ofstream out("benchmark_metrics.json"); out << std::setprecision(17) << "{\n\"schema_version\":2,\n";
    for(auto p:totals) { out << quote(p.first) << ':'; if(std::isfinite(p.second)) out << p.second; else out << "null"; out << ",\n"; }
    out << "\"min_concentration\":"; if(std::isfinite(o.min_concentration)) out << o.min_concentration; else out << "null"; out << ",\n";
    out << "\"sampling\":" << quote(state().diagnostics?"each_diffusion_step":"initial_final") << ",\n\"exception\":" << quote(exception) << ",\n\"diagnostic_flags\":[";
    bool first=true; for(auto issue:o.issues) { if(!first) out << ','; out << quote(issue); first=false; }
    out << "]\n}\n";
}
}
#endif
