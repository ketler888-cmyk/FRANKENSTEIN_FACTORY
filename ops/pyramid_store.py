import os, json, time, glob
from pathlib import Path

# Lightweight "pyramid storage":
# Level 1: SQLite/DuckDB table with summary metrics (fast query)
# Level 2: Only for top-N: keep trades/equity CSV (or Parquet) + run json

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", default="results")
    ap.add_argument("--db", default="results_ga/pyramid.duckdb")
    ap.add_argument("--top_n", type=int, default=200)
    args = ap.parse_args()

    try:
        import duckdb
    except Exception as e:
        raise SystemExit("duckdb not installed: pip install duckdb") from e

    results_dir = Path(args.results_dir)
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    con.execute("""
      create table if not exists runs(
        ts double,
        pair varchar,
        run_file varchar,
        score double,
        net double,
        dd double,
        trades integer,
        extras json
      )
    """)

    run_files = sorted(results_dir.glob("run_*.json"))
    inserted = 0
    for rf in run_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            continue
        pair = str(data.get("pair") or data.get("symbol") or "NA")
        score = float(data.get("score") or data.get("net_minus_fees") or data.get("net") or 0.0)
        net   = float(data.get("net_minus_fees") or data.get("net") or 0.0)
        dd    = float(data.get("max_dd") or data.get("max_drawdown") or 0.0)
        trades= int(data.get("trades") or data.get("n_trades") or 0)

        extras = {k:v for k,v in data.items() if k not in ("trades","n_trades","max_dd","max_drawdown","net","net_minus_fees","pair","symbol","score")}
        con.execute("insert into runs values (?,?,?,?,?,?,?,?)",
                    [time.time(), pair, str(rf).replace("\\","/"), score, net, dd, trades, json.dumps(extras, ensure_ascii=False)])
        inserted += 1

    # Keep table compact-ish: retain best top_n per pair by score
    con.execute("""
      create or replace table runs_compact as
      select * from (
        select *, row_number() over(partition by pair order by score desc) as rn
        from runs
      ) where rn <= ?
    """, [args.top_n])

    con.execute("delete from runs")
    con.execute("insert into runs select ts,pair,run_file,score,net,dd,trades,extras from runs_compact")
    con.execute("drop table runs_compact")

    con.close()
    print(f"[pyramid_store] inserted={inserted} db={db_path}")

if __name__ == "__main__":
    main()
