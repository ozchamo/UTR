
# APIs at https://blakestevenson.github.io/utr-api-docs/
# API endpoint is https://agw-prod.myutr.com
# UTR has changed their endpoint to https://agw-prod.myutr.com. 
# You may use the "JWT" cookie from your user session as a bearer token to authenticate requests.


import json, yaml
import os
import sys
from urllib.parse import parse_qs
import urllib3 
from bs4 import BeautifulSoup
import re
from flask import Flask, render_template, redirect, request, url_for, make_response
from datetime import datetime

player_db = {} # This dict will hold players by id, for data lookup like so: {}
player_track_list = []

def retrieve_token():
    utr_token = os.environ.get('UTR_TOKEN', '')
    if utr_token == '':
        # We'll check if there is a file in this same directory... 
        if os.path.isfile('UTR_TOKEN'):
            with open('UTR_TOKEN') as f:
                utr_token = f.read().rstrip("\n") #This 
    return(utr_token)


def retrieve_player_by_id(playerid):

    api_url ="https://agw-prod.myutr.com/v2/player/" + str(playerid)
    utr_token = retrieve_token()

    http = urllib3.PoolManager()

    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + utr_token
    }

    print ("Searching by ID: " + str(playerid))
    response = http.request('GET', api_url, headers = headers)
    
    return(json.loads(response.data.decode("utf-8")))
   

def retrieve_player_by_name(fullname, location, ignoreunrated, strictnamechecking, dump="no"):

    global player_db

    #defining it to return it
    playerlist = []
    
    # We'll split the name and search first and last
    fullnameaslist = fullname.split()

    # Here go the Tennis Australia exceptions
   
    print("[",fullnameaslist,"]")
    if fullnameaslist[0] == "Maindraw":
        fullnameaslist.pop(0)
    
    # We look for numbers that tournaments.tennis.com.au tends to add, like seeds
    for idx, word in enumerate(fullnameaslist):
        if word.isdigit():
            fullnameaslist.pop(idx)
        if word[0] == "[":
            fullnameaslist.pop(idx)
  
    if len(fullnameaslist) > 1:
        searchname = fullnameaslist[0] + " " + fullnameaslist[-1]
        searchfirstname = fullnameaslist[0]
        searchlastname = fullnameaslist[-1]
    else:
        searchname = fullnameaslist[0]
        searchfirstname = fullnameaslist[0]
        searchlastname = fullnameaslist[0]
    
     # Returns a list of hits as ("fullname", UTR, "Location")
    utr_token = os.environ.get('UTR_TOKEN', '')
    if utr_token == '':
        # We'll check if there is a file in this same directory... 
        if os.path.isfile('UTR_TOKEN'):
            with open('UTR_TOKEN') as f:
                utr_token = f.read().rstrip("\n") #This 

    api_url = "https://agw-prod.myutr.com/v2/search/players"
    
    http = urllib3.PoolManager()

    # DEBUGGING?
    #api_url ="https://agw-prod.myutr.com/v2/player/956231"
    #headers = {
    #    "Accept": "application/json",
    #    "Authorization": "Bearer " + utr_token
    #}
    #print ("Searching by name for DEBUG: " + str(searchname))
    #response = http.request('GET', api_url, headers = headers)
    #print("[",str(response.data.decode('utf8')),"]")
    #exit()
    # DEBUGGING?

    if utr_token == "":
        response = http.request('GET', api_url, fields={"query":searchname})
    else:
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + utr_token
        }
        print ("Searching by name: " + str(searchname))
        response = http.request('GET', api_url, fields={"query":searchname}, headers = headers)

    if dump == "yes":
        # This is used in "dump_player_info" only
        return json.loads(response.data)

    playerinfo = json.loads(response.data.decode("utf-8"))
 
    hitcount = playerinfo["total"]

    if hitcount == 0:
        print(searchname + " not found")
        # Player does not exist in the DB
        if ignoreunrated == "no":
            playerrating = "0.00"
            playerlist.append((searchname, "Player not found in UTR database", 0.00))
        return(playerlist)

    if hitcount > 100:
        print ("More than 100 records found - restricting to 100 hits")
        hitcount = 100

    for hit in range(hitcount):        
  
        try:
            playerfirstname = playerinfo["hits"][hit]["source"]["firstName"]
        except:
            playerfirstname = searchfirstname

        try:
            playerlastname = playerinfo["hits"][hit]["source"]["lastName"]
        except:
            playerlastname = searchlastname

        try:
            playerfullname = playerinfo["hits"][hit]["source"]["displayName"]
        except:
            playerfullname = fullname

        if strictnamechecking == "yes":
            # re.sub is Adrian Yip's fault as his first name was stored as "Adrian "
            if re.sub(' +', ' ', fullname.upper()) != re.sub(' +', ' ', playerfullname.upper()):
                # We've tried to match the player's fullname as display name - problem found with Pratham Om Pathak!
                if playerfirstname.upper().split()[0] != searchfirstname.upper() or playerlastname.upper() != searchlastname.upper():
                    print("Player name did not match strictnamechecking " + playerfirstname.upper() + " " + playerlastname.upper()) 
                    continue

        try:
            playername = playerinfo["hits"][hit]["source"]["displayName"]
        except:
            playername = searchname

        try:
            playerlocation = playerinfo["hits"][hit]["source"]["location"]["display"]
        except:
            playerlocation = "Unknown"

        # Ideally you would check if the token is actually useful
        #if utr_token == "":
        if playerinfo["hits"][hit]["source"]["singlesUtrDisplay"] == "0.xx":
                # 0.xx denotes that there is no UTR subscription so no goodies
                #playerrating = playerinfo["hits"][hit]["source"]["threeMonthRatingChangeDetails"]["ratingDisplay"]
                playerrating = playerinfo["hits"][hit]["source"]["threeMonthRating"]
        else:                
                #playerrating = playerinfo["hits"][hit]["source"]["myUtrSingles"]
                playerrating = playerinfo["hits"][hit]["source"]["singlesUtrDisplay"]

        if playerrating == None or playerrating == "0.00" or playerrating == "0.xx" or playerrating == 0.0 or playerrating == "Unrated":
            if ignoreunrated == "yes":
                continue
            else:
                playerrating = "0.00"

        playerratingfloat = float(playerrating)

        playerid = playerinfo["hits"][hit]["source"]["id"]

        if location == "" or playerlocation.find(location) != -1:
            # location is either "" or a string, so the above is an XOR
            print("Adding player: " + str((playername, playerlocation, playerrating, playerid)))
            player_db[str(playerid)]=[datetime.now(), playerinfo["hits"][hit]["source"]] # We add a little item in our temp DB for quick lookups
            playerlist.append((playername, playerlocation, playerratingfloat, playerid, playerinfo))

    return playerlist


def retrieve_search_parameters(request):

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

    try:
        if request.form['strictnamechecking'] == "yes":
            strictnamechecking = "yes"
    except:
        strictnamechecking = "no"

    return location, ignoreunrated, strictnamechecking


# We define the Flask app!
app = Flask(__name__, static_url_path='/static')


# =========================================================================
# Search menu
#=======================================================================

@app.route('/')
def present_search_player_form():

    playerlist = []

    cookiedata = request.cookies.get('followedplayers')
    print("COOKIE HAD", cookiedata)

    if cookiedata != None:
        followedplayers = json.loads(cookiedata)
        print("COOKIE HAD", followedplayers)

        for playerid in followedplayers:
          print("DETAIL", type(playerid))
          playerinfo = retrieve_player_by_id(playerid)
          print("DETAIL", playerinfo["displayName"],playerinfo["singlesUtr"])
          playerlist.append((playerinfo["displayName"],playerinfo["singlesUtr"]))

    return render_template('main-page.html', header = "UTR Group Search ", playerlist = playerlist)

@app.route('/navigate_search_selection', methods=['POST'])
def navigate_search_selection():

    searchselection = request.form['searchoption']

    if searchselection == "searchbynamelist":
        return(render_template('searchplayersbyname.html', header="UTR Group Search by Player Name(s)"))
    if searchselection == "searchbyurl":
        return(render_template('searchplayersbyeventurl.html', header = "UTR Group Search by Event URL"))
    if searchselection == "searchplayerjson":
        return(render_template('searchplayerbyjson.html', header = "UTR JSON single player"))


#=======================================================================
# Search by name list
#=======================================================================

@app.route('/search_players_by_name')
def present_search_player_by_names():
    return render_template('searchplayersbyname.html')
 
@app.route('/search_players_by_name_post', methods=['POST'])
def present_search_player_results():

    location, ignoreunrated, strictnamechecking = retrieve_search_parameters(request)

    playerlist =[]
    textplayerlist = request.form['playernamelist'].split("\r\n")

    for player in textplayerlist:

        # Let's clean and ignore empty lines tabs etc
        player = player.replace("  ","") # tabs
        player = player.strip() # spaces

        if player == '':
            continue
        playerlist.extend(retrieve_player_by_name(player, location, ignoreunrated, strictnamechecking))
 
    # We reorder the list by UTR
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('presentresults.html', playerlist = playerlist, header = "Search Results", resultsheading = "The following players were found:")


#=======================================================================
# Search player list by URL
#=======================================================================
@app.route('/search_players_eventurl')
def present_search_player_by_url():
    return render_template('searchplayersbyeventurl.html')

@app.route('/search_players_eventurl_post', methods=['POST'])
def present_search_player_url_results():
    playerlist =[]

    location, ignoreunrated, strictnamechecking = retrieve_search_parameters(request)
    
    # We check if the URL is at least a valid URL
    http = urllib3.PoolManager()
    try:
        response = http.request('GET', request.form['eventurl'])
    except:
        return(render_template('searchplayersbyeventurl.html', header = "UTR Group Search by Event URL (invalid URL entered, try again)"))

    soup = BeautifulSoup(response.data, 'html.parser')

    eventname = soup.find('title').string
    
    for playerlink in soup.find_all("a", href=re.compile("player.aspx?")):
        playerlist.extend(retrieve_player_by_name(playerlink.get_text(), location, ignoreunrated, strictnamechecking))
    
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('presentresults.html', playerlist = playerlist, header = "Search Results", resultsheading = "EVENT: " + eventname)


#=======================================================================
# Print detailed info for a player
#=======================================================================
@app.route('/playerinfo')
def present_player_info():

    global player_db

    playerid = request.args.get("playerid")
    playerinfo = player_db[playerid][1]

    displayName = playerinfo["displayName"]
    singlesUtrDisplay = playerinfo["singlesUtrDisplay"]
    doublesUtrDisplay = playerinfo["doublesUtrDisplay"]
    threeMonthRating = playerinfo["threeMonthRating"]
    trend = playerinfo["threeMonthRatingChangeDetails"]["changeDirection"]

    gender = playerinfo["gender"]
    ageRange = playerinfo["ageRange"]
    dominantHand = playerinfo["dominantHand"]
    backhand = playerinfo["backhand"]
    homeClub = playerinfo["homeClub"]

    displayplayerinfo = re.sub(" *\[.*\] *", " ", json.dumps(playerinfo, indent=6))
    displayplayerinfo = displayplayerinfo.replace('"','')
    displayplayerinfo = displayplayerinfo.replace("{","")
    displayplayerinfo = displayplayerinfo.replace("},","")
    displayplayerinfo = displayplayerinfo.replace("}","")
    displayplayerinfo = displayplayerinfo.replace("[","")
    displayplayerinfo = displayplayerinfo.replace("],","")
    displayplayerinfo = displayplayerinfo.replace("]","")
    displayplayerinfo = displayplayerinfo.replace(",","")

    return render_template('playerinfo.html', header = "Player Snapshot: " + displayName, playerid = playerid, displayName = displayName, singlesUtrDisplay = singlesUtrDisplay, doublesUtrDisplay = doublesUtrDisplay, threeMonthRating = threeMonthRating, trend = trend, gender = gender, ageRange = ageRange, dominantHand = dominantHand, backhand = backhand, homeClub = homeClub, jsonplayerinfo = json.dumps(playerinfo, indent=6), displayplayerinfo = displayplayerinfo)




#=======================================================================
# Add tracked player to list
#=======================================================================
@app.route('/trackplayer', methods=['GET'])
def track_player():
    playerid = request.args['playerid']

    if playerid not in player_track_list:
        player_track_list.append(playerid)
        print("playerid added to the follow list:", playerid)
        
        resp = make_response("<h1>cookie is set</h1>")
        resp.set_cookie('followedplayers', json.dumps(player_track_list))
        
        return resp

    return ""


#=======================================================================
# Dump JSON for single player  *** NOT MAINTAINED IN TREE
#=======================================================================
@app.route('/playerjson')
def present_json_player_form():
    return render_template('searchplayerbyjson.html', header = "JSON Search")

@app.route('/playerjson_post', methods=['POST'])
def present_json_player_results():
    playerlist =[]
    textplayerlist = request.form['playername'].split("\r\n")
    
    for player in textplayerlist:
        if player == '':
            continue
        # Note that the yes at the end changes the output of retrieve_player to dump json for one player
        playerinfo=retrieve_player_by_name(player, "", "no", "yes", "yes" )

    if playerinfo == "":
        playerinfo = "Player not found"
    else:
        playerinfo = json.dumps(playerinfo, indent=2)
   
    return render_template('playerjson.html', playerinfo = playerinfo, header = "Single Player JSON")

#=======================================================================

# Here goes the main
if __name__ == "__main__":
    app.run(host="0.0.0.0")
