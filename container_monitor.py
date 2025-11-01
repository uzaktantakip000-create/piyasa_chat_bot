"""
Monitor messages inside Docker container database
"""
import subprocess
import time
from datetime import datetime

def get_container_message_count():
    """Get message count from worker-1 container"""
    cmd = [
        "docker", "exec", "piyasa_worker_1", "python", "-c",
        "from database import SessionLocal, Message, Bot; "
        "from sqlalchemy import func; "
        "db = SessionLocal(); "
        "total = db.query(func.count(Message.id)).scalar() or 0; "
        "bot_counts = db.query(Bot.name, func.count(Message.id)).outerjoin(Message).group_by(Bot.id, Bot.name).all(); "
        "print(f'{total}'); "
        "[print(f'{name}:{count}') for name, count in bot_counts]; "
        "db.close()"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')

    total = int(lines[0])
    bot_stats = {}
    for line in lines[1:]:
        if ':' in line:
            name, count = line.split(':')
            bot_stats[name] = int(count)

    return total, bot_stats

def main():
    print("=== 4-WORKER CONTAINER DATABASE MONITOR ===")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")

    # Get baseline
    start_count, start_bot_stats = get_container_message_count()
    print(f"Baseline: {start_count} messages")
    print(f"Bot distribution: {start_bot_stats}")
    print("\nMonitoring for 10 minutes (checkpoints at 2, 5, 10 min)...\n")

    start_time = time.time()
    checkpoints = [120, 300, 600]  # 2, 5, 10 minutes

    for checkpoint in checkpoints:
        # Wait until checkpoint
        elapsed = time.time() - start_time
        if elapsed < checkpoint:
            time.sleep(checkpoint - elapsed)

        # Get current stats
        current_count, current_bot_stats = get_container_message_count()
        new_msgs = current_count - start_count
        elapsed_min = (time.time() - start_time) / 60
        throughput = new_msgs / elapsed_min

        print(f"[{datetime.now().strftime('%H:%M:%S')}] After {elapsed_min:.1f} min:")
        print(f"  Total: {current_count} messages (+{new_msgs})")
        print(f"  Throughput: {throughput:.2f} msg/min")
        print(f"  Bot new messages:")
        for bot_name, count in current_bot_stats.items():
            new_count = count - start_bot_stats.get(bot_name, 0)
            print(f"    {bot_name}: +{new_count}")
        print()

    # Final results
    final_count, final_bot_stats = get_container_message_count()
    new_msgs = final_count - start_count
    elapsed_min = (time.time() - start_time) / 60
    throughput = new_msgs / elapsed_min

    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Duration: {elapsed_min:.1f} minutes")
    print(f"Start messages: {start_count}")
    print(f"Final messages: {final_count}")
    print(f"New messages: {new_msgs}")
    print(f"Average throughput: {throughput:.2f} msg/min")
    print(f"\nTarget: 6.0 msg/min (4x baseline 1.5 msg/min)")

    if throughput >= 6.0:
        print("STATUS: SUCCESS - Target achieved!")
    elif throughput >= 4.0:
        print("STATUS: PARTIAL SUCCESS - 2.5x+ improvement")
    else:
        print("STATUS: BELOW TARGET - Further optimization needed")

    print("\nBot Distribution:")
    for bot_name, count in final_bot_stats.items():
        new_count = count - start_bot_stats.get(bot_name, 0)
        percentage = (new_count / new_msgs * 100) if new_msgs > 0 else 0
        print(f"  {bot_name}: {new_count} messages ({percentage:.1f}%)")

    # Save results
    with open("4worker_test_results.txt", "w") as f:
        f.write(f"4-Worker Performance Test Results\n")
        f.write(f"==================================\n\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {elapsed_min:.1f} minutes\n")
        f.write(f"Workers: 4\n")
        f.write(f"Database: PostgreSQL (Docker)\n")
        f.write(f"Redis L2 Cache: Enabled\n\n")
        f.write(f"Results:\n")
        f.write(f"  Start messages: {start_count}\n")
        f.write(f"  Final messages: {final_count}\n")
        f.write(f"  New messages: {new_msgs}\n")
        f.write(f"  Throughput: {throughput:.2f} msg/min\n\n")
        f.write(f"Comparison:\n")
        f.write(f"  Session 5 (1 worker, no cache): 1.4 msg/min\n")
        f.write(f"  Session 6 (1 worker, L1 cache): 1.5 msg/min\n")
        f.write(f"  Session 7 (4 workers, L1+L2): {throughput:.2f} msg/min\n\n")
        improvement_vs_s6 = ((throughput / 1.5) - 1) * 100
        f.write(f"Improvement vs Session 6: {improvement_vs_s6:+.1f}%\n")

    print("\nResults saved to 4worker_test_results.txt")

if __name__ == "__main__":
    main()
