#!/bin/bash
# run_pathways_benchmark.sh
# ICML-grade parallel benchmark execution with monitoring

set -e

echo "=========================================="
echo "PATHWAYS Benchmark - Parallel Execution"
echo "=========================================="

# Configuration
BENCHMARK_FILE="${1:-pathways_tasks_v3.json}"
NUM_RUNS="${2:-3}"
MAX_BROWSERS="${3:-10}"
MAX_API="${4:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="./pathways_parallel_${TIMESTAMP}"

echo ""
echo "Configuration:"
echo "  Benchmark: $BENCHMARK_FILE"
echo "  Runs: $NUM_RUNS"
echo "  Max browsers: $MAX_BROWSERS"
echo "  Max API calls: $MAX_API"
echo "  Output: $OUTPUT_DIR"
echo ""

# Check dependencies
echo "Checking dependencies..."
python3 -c "import httpx" 2>/dev/null || {
    echo "Installing httpx..."
    pip install httpx --break-system-packages
}

python3 -c "import playwright" 2>/dev/null || {
    echo "Installing playwright..."
    pip install playwright --break-system-packages
    playwright install chromium
}

# Verify benchmark file exists
if [ ! -f "$BENCHMARK_FILE" ]; then
    echo "ERROR: Benchmark file not found: $BENCHMARK_FILE"
    exit 1
fi

# Count total tasks
TOTAL_TASKS=$(python3 -c "import json; print(len(json.load(open('$BENCHMARK_FILE'))['tasks']))")
MODELS=6
CONDITIONS=4
TOTAL_RUNS=$((TOTAL_TASKS * MODELS * CONDITIONS * NUM_RUNS))

echo ""
echo "Execution Plan:"
echo "  Tasks in benchmark: $TOTAL_TASKS"
echo "  Models: $MODELS (gemini, gpt, opus, grok, qwen32b, qwen235b)"
echo "  Conditions: $CONDITIONS (explicit, hint, minimal, adversarial)"
echo "  Runs per config: $NUM_RUNS"
echo "  Total agent runs: $TOTAL_RUNS"
echo ""

# Estimate time
EST_SECONDS_PER_TASK=180
EST_PARALLEL_TIME=$((TOTAL_RUNS * EST_SECONDS_PER_TASK / MAX_BROWSERS))
EST_HOURS=$((EST_PARALLEL_TIME / 3600))

echo "Estimated completion time: ~${EST_HOURS} hours (with ${MAX_BROWSERS} parallel browsers)"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting benchmark..."
echo "  Start time: $(date)"
echo "  Output directory: $OUTPUT_DIR"
echo ""

# Run the benchmark
python3 pathways_parallel.py \
    --benchmark "$BENCHMARK_FILE" \
    --runs "$NUM_RUNS" \
    --output "$OUTPUT_DIR" \
    --max-browsers "$MAX_BROWSERS" \
    --max-api "$MAX_API" \
    2>&1 | tee "${OUTPUT_DIR}_console.log"

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Benchmark completed successfully"
    echo "  End time: $(date)"
    echo "  Results: ${OUTPUT_DIR}/all_results.json"
    echo "  Logs: ${OUTPUT_DIR}/logs/"
    echo ""
    echo "Next steps:"
    echo "  1. Run analysis: python pathways_analysis.py --results ${OUTPUT_DIR}/all_results.json"
    echo "  2. Check logs: tail -f ${OUTPUT_DIR}/logs/master.log"
    echo "  3. Monitor progress: tail -f ${OUTPUT_DIR}/progress.log"
else
    echo "✗ Benchmark failed with exit code: $EXIT_CODE"
    echo "  Check logs: ${OUTPUT_DIR}/logs/master.log"
fi
echo "=========================================="

exit $EXIT_CODE