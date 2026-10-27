// Diagnostic-only hook for an isolated build; never included by production code.
// Call after a primary solve with the model and its reaction-to-column mapping.
#include <fstream>
#include <iomanip>
#include <map>
#include <string>
inline void probe_failed_lp(const ClpSimplex& problem, const std::map<std::string,int>& columns) {
    static bool captured=false;
    if (captured || problem.isProvenOptimal()) return;
    captured=true;
    problem.writeLp("failed_problem","lp",1e-12,8,17);
    std::ofstream bounds("failed_bounds.csv");
    bounds << "reaction,column,lower,upper\n" << std::setprecision(17);
    for(auto p:columns) bounds << p.first << ',' << p.second << ',' << problem.columnLower()[p.second] << ',' << problem.columnUpper()[p.second] << '\n';
    std::ofstream report("lp_probe.csv");
    report << "experiment,reaction,required_lower,status,objective\n" << std::setprecision(17);
    ClpSimplex cold(problem); cold.setLogLevel(0); cold.allSlackBasis(); cold.primal();
    report << "cold_primal,,0," << cold.status() << ',' << cold.objectiveValue() << '\n';
    for(auto p:columns) {
        const double lower=problem.columnLower()[p.second];
        if(lower<=0) continue;
        ClpSimplex relaxed(problem); relaxed.setLogLevel(0);
        relaxed.setColumnLower(p.second,0);
        for(int i=0;i<relaxed.numberColumns();++i) relaxed.setObjectiveCoefficient(i,0);
        relaxed.setObjectiveCoefficient(p.second,1); relaxed.setOptimizationDirection(-1);
        relaxed.allSlackBasis(); relaxed.primal();
        report << "relax_required_lower_and_maximize," << p.first << ',' << lower << ',' << relaxed.status() << ',' << relaxed.objectiveValue() << '\n';
    }
}
