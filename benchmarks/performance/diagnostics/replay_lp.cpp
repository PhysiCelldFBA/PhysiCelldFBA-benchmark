// Standalone counterfactual: solve an exported LP, then change ONE column bound.
// Usage: replay_lp FILE.lp COLUMN_NAME NEW_LOWER_BOUND
#include <coin/ClpSimplex.hpp>
#include <cstdlib>
#include <iomanip>
#include <iostream>
int main(int argc,char** argv) {
    if(argc!=4) return 2;
    ClpSimplex problem; problem.setLogLevel(0);
    if(problem.readLp(argv[1],1e-12)) return 3;
    // LP import can reorder columns: resolve the exported name, never its index.
    int column=-1;
    for(int i=0;i<problem.numberColumns();++i)
        if(problem.columnName(i)==argv[2]) column=i;
    if(column<0) return 4;
    problem.allSlackBasis(); problem.primal();
    std::cout << std::setprecision(17) << "original_status=" << problem.status() << '\n';
    std::cout << "original_lower_bound=" << problem.columnLower()[column] << '\n';
    problem.setColumnLower(column,std::atof(argv[3]));
    problem.allSlackBasis(); problem.primal();
    std::cout << "modified_lower_bound=" << problem.columnLower()[column] << '\n';
    std::cout << "modified_status=" << problem.status() << '\n';
    std::cout << "modified_objective=" << problem.objectiveValue() << '\n';
    return 0;
}
