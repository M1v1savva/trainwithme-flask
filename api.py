import time
import logging
import pymongo
from flask import Flask, request, jsonify, session
from flask_cors import CORS, cross_origin
import requests
from os import environ 
import hashlib

api = Flask(__name__)
cors = CORS(api)
api.config['CORS_HEADERS'] = 'Content-Type'

client = pymongo.MongoClient(environ.get('MONGODB_TOKEN'))
db = client.get_database('trainwithme')
standings_db = db['standings']

def request_ranks(handles):
    x = requests.get('https://codeforces.com/api/user.info?handles=' + ';'.join(handles)).json()

    status = x['status']
    
    if status != 'OK':
        return ['no user']

    ans = []
    user_data = x['result']

    for user in user_data:    
        if 'rank' in user:
            ans.append(user['rank'])
        else:
            ans.append('unrated')
    return ans

def build_message(handle):
    res = standings_db.find_one({'handle': handle})
    return res['stat']

@api.route('/search', methods=["POST"])
def search_handle():
    handle = request.json.get("handle", None)
    rank = request_ranks([handle])[0]
    if rank == 'no user':
        return {"rank": rank, "message": build_message}
    
    return {"rank": rank, "message": build_message(handle)}

def fill_ranks(data):
    handle_list = []
    for i in range(len(data)):
        handle_list.append(data[i]['handle'])
    ranks = request_ranks(handle_list)
    for i in range(len(data)):
        data[i]['rank'] = ranks[i]

    return data

def fill_positions(data):
    cnt_score = dict()
    for i in range(len(data)):
        print(data[i])
        cnt_score[data[i]["score"]] = 0
    for i in range(len(data)):
        cnt_score[data[i]["score"]] += 1

    shift = 0
    for i in range(len(data)):
        if i != 0 and data[i]["score"] != data[i - 1]["score"]:
            shift += cnt_score[data[i - 1]["score"]]
        if cnt_score[data[i]["score"]] > 1:
            data[i]["position"] = "{}-{}".format(shift + 1, shift + cnt_score[data[i]["score"]])
        else:
            data[i]["position"] = "{}".format(shift + 1)
    return data


def Sha512Hash(Password):
    HashedPassword=hashlib.sha512(Password.encode('utf-8')).hexdigest()
    return HashedPassword

def build_table_data():
    t = int(time.time())
    r = '123456'
    xxx=environ.get('PUBLIC_KEY')
    yyy=environ.get('SECRET_KEY')

    if yyy == None: 
        print('did not load .env')

    myhash='123456/contest.standings?apiKey={}&contestId=393401&showUnofficial=true&time={}#{}'.format(
        xxx, t, yyy
    )
    url='https://codeforces.com/api/contest.standings?contestId=393401&showUnofficial=true&apiKey={}&time={}&apiSig=123456{}'.format(
        xxx, t, Sha512Hash(myhash)
    )

    import requests
    x = requests.get(url).json()
    status = x['status']
    if status != 'OK':
        print('api returned %s' % status)
    user_data = x['result'] 
    rows = user_data['rows']
    ans = []
    for row in rows:
        cur_handle = row['party']['members'][0]['handle']
        cur_rank = row['rank']
        bads = []
        acs = []
        for result in row['problemResults']:
            bad_attempts = result['rejectedAttemptCount']
            accepted = (1 if result['points'] != 0 else 0)
            bads.append(bad_attempts)
            acs.append(accepted)
        current_score = sum(acs)

        results_list = []
        for (is_ac, num_bad) in zip(acs, bads):
            if is_ac == 1:
                results_list.append(num_bad)
            elif num_bad > 0:
                results_list.append(-num_bad)
            else:
                results_list.append('')

        next_user = {"handle": cur_handle, "rank": "", "position": "", "score": current_score, "results": results_list}
        ans.append(next_user)
    ans = fill_ranks(ans)
    ans = fill_positions(ans)
    return ans
    
def update_database():
    data = build_table_data()
    stat = dict()
    for user in data:
        stat[user['handle']] = '#{} in the standings with {} out of 20 problems solved.'.format(user['position'], user['score'])
    
    for key in stat.keys():
        standings_db.update_one({'handle': key}, { "$set": { 'stat': stat[key] } })

update_database()

@api.route('/standings', methods=["POST"])
def get_standings():
    return {"tableData": build_table_data()}