Revised Warm-Up Submission
==========================

Contents
- generated/WarmUp_Revised_Technical_Report.pdf
- generate_revised_report.py
- generated/live_run_summary.json
- logs/
- searchclient_python/
- levels/
- server.jar

Quick start
1. Read generated/WarmUp_Revised_Technical_Report.pdf
2. Run from searchclient_python/:
   java -jar ../server.jar -l ../levels/SAsimple2.lvl -c "python3 main.py -astar --max-memory 4096" -t 60 -s 0
3. Replay an official server log for video recording:
   java -jar server.jar -r submission_artifacts/logs/MAthomasAppartment_astar_replay_2026-04-26.log -g -p -s 200

Notes
- The report explains the phased decomposition algorithm in detail.
- The stored benchmark JSON underreports phased runs; use the live logs and report discussion for cumulative phase data.
