import json
from requests_oauthlib import OAuth1Session
from dateutil.parser import parse as dateutil_parser
import datetime
from dateutil.relativedelta import relativedelta
import pyqubo as pyq
import openjij as oj
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

game_id = {'0': '馬娘', '1': 'バンドリ', '2': '原神', '3': 'プロジェクトセカイ', '4': 'パズドラ'}

# APIキーの設置
CONSUMER_KEY = 'xxxxx'
CONSUMER_SECRET = 'xxxxx'
ACCESS_TOKEN = 'xxxxx'
ACCESS_SECRET = 'xxxxx'

twitter = OAuth1Session(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
url = "https://api.twitter.com/1.1/search/tweets.json"

# 各ガチャの最高レアの期待値（100円あたり）
gacha_percent_dic = {'0': 0.865, '1': 0.882, '2': 0.186, '3': 0.952, '4': 0.976}

def kitaichi(game_name):
    tweets = []

    # パラメーター取得
    gacha_percent = gacha_percent_dic[game_name]
    keyword = game_id[game_name] + " ガチャ" + " 当たった"
    today = datetime.datetime.today()
    since_dt = today - relativedelta(months=1)
    since_dt = str(since_dt).split(".")[0]
    since_dt = dateutil_parser(since_dt + "+00:00")

    params = {'q': keyword, 'count': 100}
    req = twitter.get(url, params=params)

    if req.status_code == 200:
        search_timeline = json.loads(req.text)
        for tweet in search_timeline['statuses']:
            dt = dateutil_parser(tweet.get("created_at")) + datetime.timedelta(hours=9)
            if dt >= since_dt:
                tweets.append(tweet['id'])
    else:
        print("ERROR: %d" % req.status_code)

    kitaichi = len(tweets) * gacha_percent
    return kitaichi

def optimize(game_type, W, c, w, min_count):
    N = len(w)
    # x_max = {k: int(W / v) for k, v in w.items()}

    offset_value = {x: min_count[x] * y for x, y in w.items()}
    x_max = {k: int((W - sum(offset_value)) / v) for k, v in w.items()}

    for k, v in x_max.items():
        if v <= 0:
            return "paramater error"

    # print("x_max: ")
    # print(x_max)

    x = pyq.Array([pyq.LogEncInteger('x_{}'.format(i), (0, x_max[i])) for i in x_max.keys()])
    y = pyq.LogEncInteger('y', (0, W))
    A, B = pyq.Placeholder("A"), pyq.Placeholder("B")
    HA = pyq.Constraint(A * (W - sum(w[a] * x[a] for a in range(N)) - y) ** 2, label='HA')
    HB = -B * sum(c[a] * x[a] for a in range(N))
    Q = HA + HB
    model = Q.compile()

    feed_dict = {'A': 1, 'B': 1}
    qubo, offset = model.to_qubo(feed_dict=feed_dict)
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo)

    def decode_solution(sampleset):
        decoded = model.decode_sampleset(response, feed_dict=feed_dict)
        solution = decoded[0].subh
        x = np.zeros(N, dtype=int)
        y = 0
        for k, v in solution.items():
            if 'x' in k:
                index = int(k.split('_')[1])
                x[index] = v
            elif 'y' in k:
                y = v
        return {'x': x, 'y': y}

    result = decode_solution(response)

    print(result['x'])
    result_x = result['x']

    # gacha_count = {v: result_x[k] for k,v in game_type.items()}
    # print(gacha_count)
    gacha_count = {game_id[str(v)]: result_x[k] + min_count[k] for k, v in enumerate(game_type)}
    print(gacha_count)

    for k, v in gacha_count.items():
        print(k)
        print(v)
        print('回引く')

    return gacha_count


app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET', 'POST'])
def do_Post():
    gacha_bid = {'0': 347, '1': 340, '2': 320, '3': 315, '4': 717}

    mode = request.json['mode']
    if mode == 0:
        input_c = request.json['c']
    elif mode == 1:
        input_c = gacha_percent_dic
    elif mode == 2:
        input_c = {k: kitaichi(k) for k, v in game_id.items()}
    else:
        return "paramater error"

    min_count = request.json['min']
    game_type = request.json['game']
    W = request.json['moneyValue']

    print("input_c:")
    print(input_c)
    print("game_type:")
    print(game_type)
    print("W:")
    print(W)

    # game_type = {0:'0', 1:'1', 2:'2'}
    # c = {'0':5, '1':1, '2':3 }
    # W = 3000

    # Integer variable array
    w = {k: gacha_bid[str(v)] for k,v in enumerate(game_type)}
    c = {k: input_c[str(v)] for k,v in enumerate(game_type)}
    min_count = {k: min_count[str(v)] for k,v in enumerate(game_type)}
    print("w:")
    print(w)
    print("c:")
    print(c)

    result = optimize(game_type, W, c, w, min_count)
    if result == 'paramater error':
        return result
    resultstr = {k: str(v) for k, v in result.items()}

    return jsonify(resultstr)

if __name__ == "__main__":
    app.run(debug=True)
