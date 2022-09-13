
# APIs at https://blakestevenson.github.io/utr-api-docs/
# API endpoint is https://agw-prod.myutr.com

import json
import os
import sys
import urllib3
from bs4 import BeautifulSoup
import re
from flask import Flask, render_template, redirect, request, url_for, make_response

location = ""
ignoreunrated = "no"

def retrieve_player(fullname, dump="no"):

    global location

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

    if dump == "yes":
        # This is used in "dump_player_info" only
        return json.loads(response.data)

    playerinfo = json.loads(response.data.decode("utf-8"))
    
    hitcount = playerinfo["total"]

    if hitcount == 0:
        # Player does not exist in the DB
        playerlist.append((searchname, "Player not found in UTR database", 0.00))
        return(playerlist)

    if hitcount > 100:
        print ("More than 100 records found - restricting to 100 hits")
        hitcount = 100

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

        if playerrating == None or playerrating == "0.00"  or playerrating == "0.xx":
            if ignoreunrated == "yes":
                continue
            else:
                playerrating = "0.00"
        playerratingfloat = float(playerrating)

        playerid = playerinfo["hits"][hit]["source"]["id"]

        if playerlocation.find(location) != -1:
            # If there is a location parameter match we add to the list, else ignore
            print("Adding player: " + str((playername, playerlocation, playerrating, playerid)))
            playerlist.append((playername, playerlocation, playerratingfloat, playerid))
            #playerlist.append((playername, playerlocation, playerrating, playerid))

    return playerlist


# We define the Flask app!
app = Flask(__name__, static_url_path='/static')


# =========================================================================
# Search menu
#=======================================================================

@app.route('/')
def present_search_player_form():
    return render_template('searchoptions.html', header = "UTR Group Search options")

@app.route('/navigate_search_selection', methods=['POST'])
def navigate_search_selection():

    global location 
    global ignoreunrated 

    try:
        if request.form['location'] == "australiaonly":
            location = "Australia"
    except:
        location = ""

    try:
        if request.form['ignoreunrated'] == "yes":
            ignoreunrated = "yes"
    except:
        ignoreunrated = "no"
       
    searchselection = request.form['searchoption']
    
    if searchselection == "searchbynamelist":
        return(render_template('searchplayersbynames.html', header="UTR Group Search by Player Name(s)"))
    if searchselection == "searchbyurl":
        return(render_template('searchplayersbyeventurl.html', header = "UTR Group Search by Event URL"))
    if searchselection == "searchplayerjson":
        return(render_template('dumpplayerinfo.html', header = "UTR Single player JSON download"))


#=======================================================================
# Search by name list
#=======================================================================

@app.route('/search_player_names')
def present_search_player_by_names():
    return render_template('searchplayersbynames.html')
 
@app.route('/search_player_names_post', methods=['POST'])
def present_search_player_results():
    playerlist =[]
    textplayerlist = request.form['playernamelist'].split("\r\n")
    
    for player in textplayerlist:
        if player == '':
            continue
        playerlist.extend(retrieve_player(player))

    # We reorder the list by UTR
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('results.html', playerlist = playerlist, header = "Search Results")


#=======================================================================
# Search player list by URL
#=======================================================================
@app.route('/search_player_url')
def present_search_player_by_url():
    return render_template('searchplayersbyeventurl.html')

@app.route('/search_player_eventurl_post', methods=['POST'])
def present_search_player_url_results():
    playerlist =[]

    http = urllib3.PoolManager()
    response = http.request('GET', request.form['eventurl'])
    soup = BeautifulSoup(response.data, 'html.parser')
    
    for playerlink in soup.find_all("a", href=re.compile("player.aspx?")):
        print(playerlink.get_text())
        playerlist.extend(retrieve_player(playerlink.get_text()))
    
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('results.html', playerlist = playerlist, header = "Search Results")


#=======================================================================
# Dump JSON for single player
#=======================================================================
@app.route('/dump_player_info')
def present_dump_player_form():
    return render_template('dumpplayerinfo.html')

@app.route('/dump_player_post', methods=['POST'])
def present_dump_player_results():
    playerlist =[]
    textplayerlist = request.form['playername'].split("\r\n")
    
    for player in textplayerlist:
        if player == '':
            continue
        # Note that the yes at the end changes the output of retrieve_player to dump json for one player
        playerinfo=retrieve_player(player, "yes" )

    if playerinfo == "":
        playerinfo = "Player not found"
    else:
          playerinfo = json.dumps(playerinfo, indent=2)
   
    return render_template('dumpresults.html', playerinfo = playerinfo, header = "Single Player JSON")

#=======================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0")
