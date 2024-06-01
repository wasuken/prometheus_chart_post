import requests
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from discord import SyncWebhook, File
from datetime import datetime, timedelta
import json
import sys


def read_config(config_file):
    conifg = None
    with open(config_file, "r") as f:
        config = json.load(f)

    return config


def get_yesterday_timestamps():
    # 現在の日付と時間を取得
    now = datetime.now()

    # 昨日の日付を計算
    yesterday = now - timedelta(days=1)

    # 昨日の00:00:00と23:59:59のタイムスタンプを計算
    start_of_yesterday = datetime(
        yesterday.year, yesterday.month, yesterday.day, 0, 0, 0
    )
    end_of_yesterday = datetime(
        yesterday.year, yesterday.month, yesterday.day, 23, 59, 59
    )

    # Unixタイムスタンプに変換
    start_timestamp = start_of_yesterday.timestamp()
    end_timestamp = end_of_yesterday.timestamp()

    return start_timestamp, end_timestamp


def generate_chart_png(metric_name, config, start_timestamp, end_timestamp):
    params = {
        "query": config[metric_name]["query"],
        "start": start_timestamp,
        "end": end_timestamp,
        "step": config[metric_name]["step"],
    }
    if metric_name == "cpu":
        generate_cpu_chart_png(
            config["prometheus_url"], params, f'/tmp/chart_{metric_name}.png'
        )
    elif metric_name == "memory":
        generate_memory_chart_png(
            config["prometheus_url"], params, f'/tmp/chart_{metric_name}.png'
        )
    elif metric_name == "network":
        generate_network_chart_png(
            config["prometheus_url"], params, f'/tmp/chart_{metric_name}.png'
        )
    elif metric_name == "disk":
        generate_disk_chart_png(
            config["prometheus_url"], params, f'/tmp/chart_{metric_name}.png'
        )
    else:
        raise Exception("Unknown metric: %s" % metric_name)


def generate_memory_chart_png(prometheus_url, params, chart_png_path):
    # Prometheusからデータを取得
    response = requests.get(prometheus_url, params=params)
    data = response.json()['data']['result']

    results = []
    for entry in data:
        metric = entry['metric']
        values = entry['values']
        instance = metric.get('instance', 'unknown')
        for value in values:
            timestamp = datetime.fromtimestamp(value[0])
            mem_value = float(value[1])
            results.append([timestamp, instance, mem_value])

    df = pd.DataFrame(results, columns=['timestamp', 'instance', 'value'])

    instances = df['instance'].unique()
    fig, ax = plt.subplots(figsize=(12, 8))

    for instance in instances:
        instance_data = df[df['instance'] == instance]
        ax.plot(instance_data['timestamp'], instance_data['value'], label=instance)
        # 最後のデータポイントの位置を取得
        last_point = instance_data.iloc[-1]
        ax.text(last_point['timestamp'], last_point['value'], instance, fontsize=9, verticalalignment='center')

    ax.set_xlabel('Time')
    ax.set_ylabel('Memory Utilization (%)')
    ax.set_title('Memory Utilization Over Time by Instance')

    # 横線を追加
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # 日付フォーマットを設定
    date_format = DateFormatter("%Y-%m-%d %H:%M:%S")
    ax.xaxis.set_major_formatter(date_format)

    # チャートの自動調整
    fig.autofmt_xdate()
    ax.legend()
    plt.savefig(chart_png_path)
    plt.close()


def generate_network_chart_png(prometheus_url, params, chart_png_path):
    # Prometheusからデータを取得
    response = requests.get(prometheus_url, params=params)
    data = response.json()['data']['result']

    results = []
    for entry in data:
        metric = entry['metric']
        values = entry['values']
        instance = metric.get('instance', 'unknown')
        # すべての値が0でない場合にのみ追加
        if any(float(value[1]) != 0 for value in values):
            for value in values:
                timestamp = datetime.fromtimestamp(value[0])
                net_value = float(value[1])
                results.append([timestamp, instance, net_value])

    df = pd.DataFrame(results, columns=['timestamp', 'instance', 'value'])

    instances = df['instance'].unique()
    fig, ax = plt.subplots(figsize=(12, 8))

    for instance in instances:
        instance_data = df[df['instance'] == instance]
        ax.plot(instance_data['timestamp'], instance_data['value'], label=instance)
        # 最後のデータポイントの位置を取得
        last_point = instance_data.iloc[-1]
        ax.text(last_point['timestamp'], last_point['value'], instance, fontsize=9, verticalalignment='center')

    ax.set_xlabel('Time')
    ax.set_ylabel('Network Receive Rate (bytes/s)')
    ax.set_title('Network Receive Rate Over Time by Instance')

    # 横線を追加
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # 日付フォーマットを設定
    date_format = DateFormatter("%Y-%m-%d %H:%M:%S")
    ax.xaxis.set_major_formatter(date_format)

    # チャートの自動調整
    fig.autofmt_xdate()
    ax.legend()
    plt.savefig(chart_png_path)
    plt.close()


def generate_disk_chart_png(prometheus_url, params, chart_png_path):
    # Prometheusからデータを取得
    response = requests.get(prometheus_url, params=params)
    data = response.json()["data"]["result"]

    results = []
    for entry in data:
        metric = entry["metric"]
        values = entry["values"]
        instance = metric["instance"]
        device = metric["device"]
        if device.find('dev') < 0 or device == ('/dev/root'):
            continue
        for value in values:
            timestamp = datetime.fromtimestamp(value[0])
            disk_value = float(value[1])
            results.append([timestamp, f"{instance}-{device}", disk_value])

    df = pd.DataFrame(
        results, columns=["timestamp", "instance-device", "value"]
    )

    # 各デバイスごとのディスク使用率をプロット
    idevices = df["instance-device"].unique()
    fig, ax = plt.subplots(figsize=(12, 8))

    for idevice in idevices:
        idevice_data = df[df["instance-device"] == idevice]
        ax.plot(
            idevice_data["timestamp"], idevice_data["value"], label=idevice
        )
        # 最後のデータポイントの位置を取得
        last_point = idevice_data.iloc[-1]
        ax.text(
            last_point["timestamp"],
            last_point["value"],
            idevice,
            fontsize=9,
            verticalalignment="center",
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Disk Usage (bytes)")
    ax.set_title("Disk Usage Over Time by Instance-Device")
    # 横線を追加
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)

    # 日付フォーマットを設定
    date_format = DateFormatter("%Y-%m-%d %H:%M:%S")
    ax.xaxis.set_major_formatter(date_format)

    # 凡例を線に寄り添わせる
    ax.legend(loc="best")

    # チャートの自動調整
    fig.autofmt_xdate()
    ax.legend()
    plt.savefig(chart_png_path)
    plt.close()


def generate_cpu_chart_png(prometheus_url, params, chart_png_path):
    # Prometheusからデータを取得
    response = requests.get(prometheus_url, params=params)
    data = response.json()['data']['result']

    results = []
    for entry in data:
        metric = entry['metric']
        values = entry['values']
        instance = metric.get('instance', 'unknown')
        for value in values:
            timestamp = datetime.fromtimestamp(value[0])
            cpu_value = float(value[1])
            results.append([timestamp, instance, cpu_value])

    df = pd.DataFrame(results, columns=['timestamp', 'instance', 'value'])

    instances = df['instance'].unique()
    fig, ax = plt.subplots(figsize=(12, 8))

    for instance in instances:
        instance_data = df[df['instance'] == instance]
        ax.plot(instance_data['timestamp'], instance_data['value'], label=instance)
        # 最後のデータポイントの位置を取得
        last_point = instance_data.iloc[-1]
        ax.text(last_point['timestamp'], last_point['value'], instance, fontsize=9, verticalalignment='center')

    ax.set_xlabel('Time')
    ax.set_ylabel('CPU Utilization (%)')
    ax.set_title('CPU Utilization Over Time by Instance')

    # 横線を追加
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # 日付フォーマットを設定
    date_format = DateFormatter("%Y-%m-%d %H:%M:%S")
    ax.xaxis.set_major_formatter(date_format)

    # チャートの自動調整
    fig.autofmt_xdate()
    ax.legend()
    plt.savefig(chart_png_path)
    plt.close()


def send_file_to_discord(webhook_url, chart_png_path, title):
    webhook = SyncWebhook.from_url(webhook_url)

    with open(chart_png_path, "rb") as f:
        webhook.send(title, file=File(f, chart_png_path))


def send_chart_png_to_discord(config_path):
    start_timestamp, end_timestamp = get_yesterday_timestamps()
    config = read_config(config_path)
    params = {
        "query": config['cpu']["query"],
        "start": start_timestamp,
        "end": end_timestamp,
        "step": "14",
    }
    for opt in ["cpu", "memory", "network", "disk"]:
        print(f"## {opt} ##")
        generate_chart_png(opt, config, start_timestamp, end_timestamp)
        send_file_to_discord(config['webhook_url'], f'/tmp/chart_{opt}.png', f"Here is the {opt} usage chart")


if __name__ == '__main__':
    # Prometheusのエンドポイントとクエリ
    if len(sys.argv) <= 0:
        print("Usage: python send_chart_png_to_discord.py <config_file>")
        return
    config_file = sys.argv[1]
    send_chart_png_to_discord(config_file)
