#include "telemetry.h"
#include <cassert>
struct LP {
    int invocations=0;
    int numberIterations() const { return 3; }
    int status() const { return 0; }
    int numberRows() const { return 7; }
    int numberColumns() const { return 9; }
    int getNumElements() const { return 11; }
};
int main() {
    using namespace PCBenchmark;
    LP lp;
    solve(lp,"stage_one",false,false,[&](){++lp.invocations;});
    assert(lp.invocations==1 && state().threads.empty());
    state().threads.resize(2); state().enabled=true;
    solve(lp,"initial_primary",true,false,[&](){++lp.invocations;});
    assert(local().values["initial_solve_calls"]==1);
    assert(local().values["initial_primary_solve_calls"]==1);
    #pragma omp parallel num_threads(2)
    {
        LP own;
        for(int i=0;i<5;++i) {
            solve(own,"stage_two",false,i==4,[&](){++own.invocations;});
            due(omp_get_thread_num()); updated(omp_get_thread_num(),nullptr);
        }
        assert(own.invocations==5);
        assert(local().values["optimization_calls"]==5);
        assert(local().values["stage_two_retries"]==1);
        assert(local().due==local().updated);
    }
    assert(state().threads[0].values["stage_two_rows_max"]==7);
}
