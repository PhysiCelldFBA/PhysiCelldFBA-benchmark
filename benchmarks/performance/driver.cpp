// Benchmark-only main. Preserve the sample's diffusion -> exchange -> FBA
// ordering and scheduler; no equality constraint or timestep correction.
#include "./core/PhysiCell.h"
#include "./modules/PhysiCell_standard_modules.h"
#include "./benchmarks/performance/runtime.h"
#include "./custom_modules/custom.h"
using namespace PhysiCell;
using namespace BioFVM;
int main(int argc, char** argv) {
    if (argc!=2) return 2;
    const double begin=PCBenchmark::clock_seconds();
    try {
        if(!load_PhysiCell_config_file(argv[1])) return 2;
        omp_set_num_threads(PhysiCell_settings.omp_num_threads);
        PCBenchmark::initialize();
        setup_microenvironment();
        create_cell_container_for_microenvironment(microenvironment,30);
        create_cell_types();
        if(PCBenchmark::options().attribute("layout").as_string()==std::string("application")) setup_tissue();
        else PCBenchmark::create_controlled_cells();
        PCBenchmark::configure_cells();
        // Preserve the cancer sample's pre-diffusion initialization. Express it
        // in physical minutes so timestep refinement does not change its length.
        const double warm_minutes=PCBenchmark::options().attribute("equilibration_minutes").as_double(
            physicell_config_root.child("user_parameters").child("diffusion_steps").text().as_int(0)*diffusion_dt);
        const int warm_steps=int(std::llround(warm_minutes/diffusion_dt));
        if (warm_minutes<0 || std::abs(warm_steps*diffusion_dt-warm_minutes)>1e-9) throw std::runtime_error("Pre-equilibration duration must align with diffusion dt");
        { PCBenchmark::Timer t("pre_equilibration_seconds");
          for(int i=0;i<warm_steps;++i) microenvironment.simulate_diffusion_decay(diffusion_dt); }
        PCBenchmark::count("pre_equilibration_steps",warm_steps);
        PCBenchmark::state().on_update=PCBenchmark::after_update;
        PCBenchmark::state().after_exchange=PCBenchmark::exchange_observation;
        PCBenchmark::state().before_exchange=PCBenchmark::before_exchange;
        set_save_biofvm_mesh_as_matlab(true); set_save_biofvm_data_as_matlab(true);
        set_save_biofvm_cell_data(true); set_save_biofvm_cell_data_as_custom_matlab(true);
        PCBenchmark::count("initialization_seconds",PCBenchmark::clock_seconds()-begin);
        auto snapshot=[](const std::string& name) {
            PCBenchmark::Timer t("output_seconds");
            save_PhysiCell_to_MultiCellDS_v2(PhysiCell_settings.folder+"/"+name,microenvironment,PhysiCell_globals.current_time);
        };
        PCBenchmark::observe("initial"); snapshot("initial");
        const double loop_start=PCBenchmark::clock_seconds();
        // Same end condition as the existing dFBA sample mains.
        while(PhysiCell_globals.current_time < PhysiCell_settings.max_time+0.1*diffusion_dt) {
            if(PhysiCell_settings.enable_full_saves && PhysiCell_globals.current_time > PhysiCell_globals.next_full_save_time-0.5*diffusion_dt) {
                snapshot("output"+std::to_string(PhysiCell_globals.full_output_index++));
                PhysiCell_globals.next_full_save_time+=PhysiCell_settings.full_save_interval;
            }
            { PCBenchmark::Timer t("diffusion_seconds"); microenvironment.simulate_diffusion_decay(diffusion_dt); }
            { PCBenchmark::Timer t("cell_container_seconds");
              ((Cell_Container*)microenvironment.agent_container)->update_all_cells(PhysiCell_globals.current_time); }
            if(PCBenchmark::state().diagnostics) { PCBenchmark::observe("after_cell_step"); PCBenchmark::flush_rows(); }
            PhysiCell_globals.current_time+=diffusion_dt;
        }
        PCBenchmark::count("simulation_loop_seconds",PCBenchmark::clock_seconds()-loop_start);
        PCBenchmark::observe("final"); snapshot("final"); PCBenchmark::finish();
        return 0;
    } catch(const std::exception& e) {
        if(PCBenchmark::state().enabled) PCBenchmark::finish(e.what());
        std::cerr << e.what() << '\n'; return 1;
    }
}
