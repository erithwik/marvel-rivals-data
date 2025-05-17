set -e
cd ~/Desktop/github/rivals
uv run data_collector.py
cd ~/Desktop/github/marvel-rivals
git add .

# Check if there are any changes staged for commit
if ! git diff --cached --quiet; then
    git commit -m "added new data"
    git push origin HEAD --no-verify --force
    echo "Pushed changes."
else
    echo "No changes to commit."
fi
