import requests
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from discord import SyncWebhook, File
from datetime import datetime, timedelta
import json

def read_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    prometheus_url = config['prometheus_url']
    webhook_url = config['webhook_url']
    query = config['query']
    chart_png_path = config['chart_png_path']

    return prometheus_url, query, chart_png_path, webhook_url


def get_yesterday_timestamps():
    # 現在の日付と時間を取得
    now = datetime.now()
    
    # 昨日の日付を計算
    yesterday = now - timedelta(days=1)
    
    # 昨日の00:00:00と23:59:59のタイムスタンプを計算
    start_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
    end_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
    
    # Unixタイムスタンプに変換
    start_timestamp = start_of_yesterday.timestamp()
    end_timestamp = end_of_yesterday.timestamp()
    
    return start_timestamp, end_timestamp



def generate_chart_png(prometheus_url, params, chart_png_path):
    # Prometheusからデータを取得
    response = requests.get(prometheus_url, params=params)
    data = response.json()['data']['result']

    results = []
    for entry in data:
        metric = entry['metric']
        values = entry['values']
        cpu = metric['cpu']
        mode = metric['mode']
        instance = metric['instance']
        for value in values:
            timestamp = datetime.fromtimestamp(value[0])
            cpu_value = float(value[1])
            results.append([timestamp, instance, cpu, mode, cpu_value])
    
    df = pd.DataFrame(results, columns=['timestamp', 'instance', 'cpu', 'mode', 'value'])
    
    # CPU利用率を計算するために各インスタンスとタイムスタンプごとにmode別の値を統合
    df_summary = df.groupby(['timestamp', 'instance', 'mode']).agg({'value': 'sum'}).reset_index()
    
    # 各インスタンスごとのCPU利用率を計算
    df_pivot = df_summary.pivot_table(index=['timestamp', 'instance'], columns='mode', values='value').reset_index()

    # 各modeの列が存在しない場合は0を代入
    for mode in ['idle', 'iowait', 'irq', 'nice', 'softirq', 'steal', 'system', 'user']:
        if mode not in df_pivot.columns:
            df_pivot[mode] = 0
    
    # 総時間とアイドル時間の差を計算
    df_pivot['total'] = df_pivot[['idle', 'iowait', 'irq', 'nice', 'softirq', 'steal', 'system', 'user']].sum(axis=1)
    df_pivot['utilization'] = (df_pivot['total'] - df_pivot['idle']) / df_pivot['total'] * 100

    
    instances = df_pivot['instance'].unique()
    fig, ax = plt.subplots(figsize=(12, 8))

    for instance in instances:
        instance_data = df_pivot[df_pivot['instance'] == instance]
        ax.plot(instance_data['timestamp'], instance_data['utilization'], label=instance)
        # 最後のデータポイントの位置を取得
        last_point = instance_data.iloc[-1]
        ax.text(last_point['timestamp'], last_point['utilization'], instance, fontsize=9, verticalalignment='center')

    ax.set_xlabel('Time')
    ax.set_ylabel('CPU Utilization (%)')
    ax.set_title('CPU Utilization Over Time by Instance')
    # 横線を追加
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # 日付フォーマットを設定
    date_format = DateFormatter("%Y-%m-%d %H:%M:%S")
    ax.xaxis.set_major_formatter(date_format)
    
    # 凡例を線に寄り添わせる
    ax.legend(loc='best')

    # チャートの自動調整
    fig.autofmt_xdate()
    ax.legend()
    plt.savefig(chart_png_path)
    plt.close()

    
def send_file_to_discord(webhook_url, chart_png_path):
    webhook = SyncWebhook.from_url(webhook_url)
    
    with open(chart_png_path, 'rb') as f:
        webhook.send("Here is the CPU usage chart", file=File(f, chart_png_path))

def send_chart_png_to_discord(prometheus_url, params, chart_png_path, webhook_url):
    generate_chart_png(prometheus_url, params, chart_png_path)
    send_file_to_discord(webhook_url, chart_png_path)

# Prometheusのエンドポイントとクエリ
config_file = 'config.json'
prometheus_url, query, chart_png_path, webhook_url = read_config(config_file)
start_timestamp, end_timestamp = get_yesterday_timestamps()
params = {
    'query': "node_cpu_seconds_total",
    'start': start_timestamp,
    'end': end_timestamp,
    'step': "14",
}

send_chart_png_to_discord(prometheus_url, params, chart_png_path, webhook_url)
