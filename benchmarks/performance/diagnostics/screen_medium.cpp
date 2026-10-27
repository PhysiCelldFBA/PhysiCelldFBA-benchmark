// One static, single-cell LP feasibility check; no PhysiCell simulation.
// Usage: screen_medium SBML OBJECTIVE GROWTH_UPPER BOUNDS_TSV OUTPUT_TSV
#include "dfba_Model.h"
#include <fstream>
#include <iomanip>
#include <set>
#include <string>
#include <cstdlib>
int main(int argc,char** argv) {
    if(argc!=6) return 2;
    dFBAModel model; model.initModel(argv[1]);
    if(!model.getReaction(argv[2])) return 3;
    model.setReactionUpperBound(argv[2],std::atof(argv[3]));
    std::ifstream bounds(argv[4]); std::string id; double lower;
    if(!bounds) return 5;
    std::set<std::string> mapped;
    while(bounds>>id>>lower) {
        if(!model.getReaction(id)) return 4;
        model.setReactionLowerBound(id,lower); mapped.insert(id);
    }
    auto solution=model.optimize();
    int implicit_uptake=0;
    for(auto reaction:model.getListOfBoundaryReactionIds())
        if(!mapped.count(reaction) && model.getReactionLowerBound(reaction)<0) ++implicit_uptake;
    std::ofstream out(argv[5]);
    if(!out) return 6;
    out << "status\tgrowth_per_hour\tunmapped_boundary_reactions_allowing_uptake\n"
        << solution.status << '\t' << std::setprecision(17) << solution.getObjectiveValue() << '\t' << implicit_uptake << '\n';
    return 0;
}
