"""
4-Worker Performance Test Monitor
Monitors message generation for 10 minutes
"""
import time
from datetime import datetime
from database import SessionLocal, Message

def main():
    db = SessionLocal()

    start_count = db.query(Message).count()
    start_time = time.time()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Test started - Baseline: {start_count} messages")
    print("Monitoring for 10 minutes...")
    print("-" * 60)

    intervals = [60, 120, 180, 240, 300, 420, 540, 600]  # 1, 2, 3, 4, 5, 7, 9, 10 minutes

    for interval in intervals:
        time.sleep(interval - (time.time() - start_time))
        current_count = db.query(Message).count()
        new_msgs = current_count - start_count
        elapsed_min = (time.time() - start_time) / 60
        throughput = new_msgs / elapsed_min

        print(f"[{datetime.now().strftime('%H:%M:%S')}] After {elapsed_min:.1f} min: {current_count} messages (+{new_msgs}, {throughput:.2f} msg/min)")

    # Final results
    final_count = db.query(Message).count()
    elapsed = time.time() - start_time
    new_msgs = final_count - start_count
    throughput = (new_msgs / elapsed) * 60

    print("-" * 60)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] TEST COMPLETED")
    print(f"  Duration: {elapsed/60:.1f} minutes")
    print(f"  Start messages: {start_count}")
    print(f"  Final messages: {final_count}")
    print(f"  New messages: {new_msgs}")
    print(f"  Throughput: {throughput:.2f} msg/min")
    print("-" * 60)

    # Save results to file
    with open("4worker_test_results.txt", "w") as f:
        f.write(f"4-Worker Performance Test Results\n")
        f.write(f"==================================\n\n")
        f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {elapsed/60:.1f} minutes\n")
        f.write(f"Workers: 4\n")
        f.write(f"Redis L2 Cache: Enabled\n\n")
        f.write(f"Results:\n")
        f.write(f"  Start messages: {start_count}\n")
        f.write(f"  Final messages: {final_count}\n")
        f.write(f"  New messages: {new_msgs}\n")
        f.write(f"  Throughput: {throughput:.2f} msg/min\n\n")
        f.write(f"Comparison to Previous Sessions:\n")
        f.write(f"  Session 5 (1 worker, no cache): 1.4 msg/min\n")
        f.write(f"  Session 6 (1 worker, L1 cache): 1.5 msg/min\n")
        f.write(f"  Session 7 (4 workers, L1+L2): {throughput:.2f} msg/min\n\n")
        improvement_vs_s5 = ((throughput / 1.4) - 1) * 100
        improvement_vs_s6 = ((throughput / 1.5) - 1) * 100
        f.write(f"Improvement:\n")
        f.write(f"  vs Session 5: {improvement_vs_s5:+.1f}%\n")
        f.write(f"  vs Session 6: {improvement_vs_s6:+.1f}%\n")

    print("Results saved to 4worker_test_results.txt")
    db.close()

if __name__ == "__main__":
    main()
