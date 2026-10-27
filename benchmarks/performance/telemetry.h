#ifndef PHYSICELL_BENCHMARK_TELEMETRY_H
#define PHYSICELL_BENCHMARK_TELEMETRY_H
// Included only by builds explicitly compiled with PHYSICELL_BENCHMARK.
// No model-specific reaction identifiers or changes to solver algorithms.
#include <chrono>
#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>
#include <omp.h>

namespace PCBenchmark {
inline double clock_seconds() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct alignas(64) ThreadData {
    std::map<std::string, double> values;
    std::map<int, unsigned long long> due, updated;
    std::vector<std::string> cell_rows, flux_rows;
};
struct State {
    bool enabled = false, fixed_population = false, fixed_volume = false, diagnostics = false;
    std::vector<ThreadData> threads;
    void (*on_update)(void*) = nullptr;
    void (*after_exchange)() = nullptr;
    void (*before_exchange)(double) = nullptr;
};
inline State& state() { static State s; return s; }
inline ThreadData& local() { return state().threads.at(omp_get_thread_num()); }
inline void count(const std::string& key, double value = 1) {
    if (state().enabled) local().values[key] += value;
}
struct Timer {
    std::string key;
    double start;
    explicit Timer(const std::string& name): key(name), start(state().enabled ? clock_seconds() : 0) {}
    ~Timer() { if (state().enabled) count(key, clock_seconds() - start); }
};
inline void due(int id) { if (state().enabled) ++local().due[id]; }
inline void updated(int id, void* cell) {
    if (!state().enabled) return;
    ++local().updated[id]; count("intracellular_updates");
    if (state().on_update) state().on_update(cell);
}
template<class LP, class Operation>
inline void solve(LP& lp, const char* stage, bool initialization, bool retry, Operation operation) {
    if (!state().enabled) { operation(); return; }
    const double start = clock_seconds();
    operation();
    const std::string prefix(stage);
    count(initialization ? "initial_solve_calls" : "optimization_calls");
    count(prefix + "_solve_calls");
    count(prefix + "_thread_seconds", clock_seconds() - start);
    count(prefix + "_iterations", lp.numberIterations());
    count(prefix + "_status_" + std::to_string(lp.status()));
    if (retry) count("stage_two_retries");
    // LP dimensions are recorded as maxima, not sums over cells or calls.
    auto& v = local().values;
    v[prefix + "_rows_max"] = std::max(v[prefix + "_rows_max"], double(lp.numberRows()));
    v[prefix + "_columns_max"] = std::max(v[prefix + "_columns_max"], double(lp.numberColumns()));
    v[prefix + "_nonzeros_max"] = std::max(v[prefix + "_nonzeros_max"], double(lp.getNumElements()));
}
}
#endif
