# -*- coding: utf-8 -*-
"""
Latency Benchmark & SLA Verification (< 3s Requirement)
推理延迟压力测试与 3 秒响应 SLA 验证脚本
"""

import os
import sys
import time
import numpy as np
import torch

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer


def run_latency_benchmark(num_iterations: int = 1000):
    print("=" * 75)
    print("  CryptoLeverageTransformer Latency Benchmark & SLA Verification")
    print(f"  Target SLA: Prediction must execute in < 3.000 seconds (3,000 ms)")
    print(f"  Benchmarking {num_iterations} real-time prediction cycles...")
    print("=" * 75)

    B, K, L, D = 1, 4, 60, 25

    # 1. GPU Benchmark (if CUDA available)
    if torch.cuda.is_available():
        device = torch.device('cuda')
        gpu_name = torch.cuda.get_device_name(0)
        print(f"\n[1/2] Benchmarking on GPU: {gpu_name}")

        model_gpu = CryptoLeverageTransformer(num_assets=K, in_features=D, lookback=L).to(device)
        model_gpu.eval()

        dummy_x = torch.randn(B, K, L, D, device=device)

        # Warm-up (50 passes)
        with torch.no_grad():
            for _ in range(50):
                _ = model_gpu(dummy_x)
        torch.cuda.synchronize()

        # Timing loop
        gpu_latencies_ms = []
        with torch.no_grad():
            for _ in range(num_iterations):
                t0 = time.perf_counter()
                out = model_gpu(dummy_x)

                # Simulate live price conversion: P_tp = P0 * (1 +/- tp_pct)
                prob_gate = out['prob_gate'][0].cpu().numpy()
                tp_pct = out['pred_tp_pct'][0].cpu().numpy()
                sl_pct = out['pred_sl_pct'][0].cpu().numpy()
                expected_roe = out['pred_expected_roe'][0].cpu().numpy()

                p0 = np.array([60000.0, 2500.0, 150.0, 550.0])
                tp_prices = p0 * (1.0 + tp_pct)
                sl_prices = p0 * (1.0 - sl_pct)

                torch.cuda.synchronize()
                t1 = time.perf_counter()
                gpu_latencies_ms.append((t1 - t0) * 1000.0)

        gpu_lat = np.array(gpu_latencies_ms)
        print(f"  GPU Benchmark Results ({num_iterations} runs):")
        print(f"    Mean Latency:   {gpu_lat.mean():.3f} ms")
        print(f"    Median (p50):   {np.percentile(gpu_lat, 50):.3f} ms")
        print(f"    p95 Latency:    {np.percentile(gpu_lat, 95):.3f} ms")
        print(f"    p99 Latency:    {np.percentile(gpu_lat, 99):.3f} ms")
        print(f"    Max Latency:    {gpu_lat.max():.3f} ms")
        print(f"    SLA Margin:     {3000.0 / gpu_lat.mean():.1f}X faster than 3s limit!")
        assert gpu_lat.max() < 3000.0, "GPU latency exceeded 3s SLA!"

    # 2. CPU Benchmark
    print(f"\n[2/2] Benchmarking on CPU (Fallback Engine)")
    device_cpu = torch.device('cpu')
    model_cpu = CryptoLeverageTransformer(num_assets=K, in_features=D, lookback=L).to(device_cpu)
    model_cpu.eval()

    dummy_x_cpu = torch.randn(B, K, L, D, device=device_cpu)

    # Warm-up (10 passes)
    with torch.no_grad():
        for _ in range(10):
            _ = model_cpu(dummy_x_cpu)

    cpu_latencies_ms = []
    num_cpu_iter = min(num_iterations, 200)
    with torch.no_grad():
        for _ in range(num_cpu_iter):
            t0 = time.perf_counter()
            out = model_cpu(dummy_x_cpu)

            prob_gate = out['prob_gate'][0].numpy()
            tp_pct = out['pred_tp_pct'][0].numpy()
            sl_pct = out['pred_sl_pct'][0].numpy()
            expected_roe = out['pred_expected_roe'][0].numpy()

            p0 = np.array([60000.0, 2500.0, 150.0, 550.0])
            tp_prices = p0 * (1.0 + tp_pct)
            sl_prices = p0 * (1.0 - sl_pct)

            t1 = time.perf_counter()
            cpu_latencies_ms.append((t1 - t0) * 1000.0)

    cpu_lat = np.array(cpu_latencies_ms)
    print(f"  CPU Benchmark Results ({num_cpu_iter} runs):")
    print(f"    Mean Latency:   {cpu_lat.mean():.3f} ms")
    print(f"    Median (p50):   {np.percentile(cpu_lat, 50):.3f} ms")
    print(f"    p95 Latency:    {np.percentile(cpu_lat, 95):.3f} ms")
    print(f"    p99 Latency:    {np.percentile(cpu_lat, 99):.3f} ms")
    print(f"    Max Latency:    {cpu_lat.max():.3f} ms")
    print(f"    SLA Margin:     {3000.0 / cpu_lat.mean():.1f}X faster than 3s limit!")
    assert cpu_lat.max() < 3000.0, "CPU latency exceeded 3s SLA!"

    print("\n" + "=" * 75)
    print(f"  VERIFICATION PASSED: All prediction cycles strictly executed in < 3s!")
    print("=" * 75)


if __name__ == '__main__':
    run_latency_benchmark()
