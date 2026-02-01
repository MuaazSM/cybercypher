#!/bin/bash

# CyberCypher Terminal Demo Runner
# Run this to see the interactive agent loop demonstration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "CyberCypher Terminal Demo"
echo "=========================================="
echo ""
echo "Choose a demo:"
echo "  1) Terminal Walkthrough (Interactive, detailed architecture walkthrough)"
echo "  2) Full Simulation (Complete incident with GitHub integration)"
echo "  3) Quick Demo (Fast version, no pauses)"
echo ""

read -p "Enter choice (1-3): " choice

cd "$PROJECT_ROOT"

case $choice in
    1)
        echo "Starting Terminal Walkthrough..."
        echo "Navigate through each agent pipeline stage."
        echo ""
        python -m demo.terminal_presenter
        ;;
    2)
        echo "Starting Full Simulation..."
        echo "Watch a complete incident flow through the system."
        echo ""
        python -m demo.simulation
        ;;
    3)
        echo "Starting Quick Demo (no pauses)..."
        python -c "
from demo.terminal_presenter import (
    TerminalPresenter, Stage, Color, Pipeline, GitHubAPI, load_env_file,
    demo_observe_pipeline,
    demo_reason_pipeline,
    demo_decide_pipeline,
    demo_act_pipeline
)
import os

# Load .env file
load_env_file()

# Setup GitHub API
github_token = os.getenv('GITHUB_TOKEN')
github_api = GitHubAPI(token=github_token)
presenter = TerminalPresenter(slow_mode=False, github_api=github_api)
pipeline = Pipeline()

presenter.print_header('CYBERCYPHER AGENT LOOP - QUICK MODE')
print('Running fast demo without pauses...\n')

demo_observe_pipeline(presenter, pipeline)
demo_reason_pipeline(presenter, pipeline)
demo_decide_pipeline(presenter, pipeline)
demo_act_pipeline(presenter, pipeline)

print('\n' + Color.GREEN + Color.BOLD + 'Demo Complete!' + Color.RESET)
"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
