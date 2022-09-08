
# APIs at https://blakestevenson.github.io/utr-api-docs/
# API endpoint is https://agw-prod.myutr.com

import json
import os
import sys
import urllib3
from flask import Flask, render_template, redirect, request, url_for, make_response

debug="no" 

def retrieve_player(fullname, location = ""):

    #defining it to return it
    playerlist = []

    # Returns a list of hits as ("fullname", UTR, "Location")
    utr_token = os.environ.get('UTR_TOKEN', '')
    if utr_token == '':
        # We'll check if there is a file in this same directory... 
        if os.path.isfile('UTR_TOKEN'):
            with open('UTR_TOKEN') as f:
                utr_token = f.read().rstrip("\n") #This 

    api_url = "https://agw-prod.myutr.com/v2/search/players"

    http = urllib3.PoolManager()

    # We'll split the name and search first and last
    fullnameaslist = fullname.split()

    # Here go the Tennis Australia exceptions
   
    if fullnameaslist[0] == "Maindraw":
        fullnameaslist.pop(0)
    
    # We look for numbers that tournaments.tennis.com.au tends to add, like seeds
    for idx, word in enumerate(fullnameaslist):
        if word.isdigit():
            fullnameaslist.pop(idx)
  
    if len(fullnameaslist) > 1:
        searchname = fullnameaslist[0] + " " + fullnameaslist[-1]
    else:
        searchname = fullnameaslist
    
    if utr_token == "":
        response = http.request('GET', api_url, fields={"query":searchname})
    else:
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + utr_token
        }
        response = http.request('GET', api_url, fields={"query":searchname}, headers = headers)

    playerinfo = json.loads(response.data.decode("utf-8"))
    
    hitcount = playerinfo["total"]

    if hitcount == 0:
        # Player does not exist in the DB
        playerlist.append((searchname, "Player not found in UTR database", "0.00"))
        return(playerlist)

    for hit in range(hitcount):        
  
        try:
            playername = playerinfo["hits"][hit]["source"]["displayName"]
        except:
            playername = searchname

        try:
            playerlocation = playerinfo["hits"][hit]["source"]["location"]["display"]
        except:
            playerlocation = "Unknown"

        if utr_token == "":
                playerrating = playerinfo["hits"][hit]["source"]["threeMonthRatingChangeDetails"]["ratingDisplay"]
        else:
                playerrating = playerinfo["hits"][hit]["source"]["singlesUtrDisplay"]
        
        if playerrating == None:
            playerrating = "N/A"

        if playerlocation.find(location) != -1:
            # If there is a location parameter match we add to the list, else ignore
            print("Adding player: " + str((playername, playerlocation, playerrating)))
            playerlist.append((playername, playerlocation, playerrating))

    return playerlist

# =========================================================================

app = Flask(__name__)

@app.route('/')
def present_search_player_form():
    return render_template('searchpage.html')

@app.route('/search_player_post', methods=['POST'])
def present_search_player_results():
    playerlist =[]
    textplayerlist = request.form['playernamelist'].split("\r\n")
    
    for player in textplayerlist:
        if player == '':
            continue
        playerlist.extend(retrieve_player(player, location="Australia" ))

    # We reorder the list by UTR
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('results.html', playerlist = playerlist)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == 'debug':
            debug="yes"
    app.run(host="0.0.0.0")
