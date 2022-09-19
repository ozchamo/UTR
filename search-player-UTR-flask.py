
# APIs at https://blakestevenson.github.io/utr-api-docs/
# API endpoint is https://agw-prod.myutr.com
# UTR has changed their endpoint to https://agw-prod.myutr.com. 
# You may use the "JWT" cookie from your user session as a bearer token to authenticate requests.


import json
import os
import sys
from urllib.parse import parse_qs
import urllib3 
from bs4 import BeautifulSoup
import re
from flask import Flask, render_template, redirect, request, url_for, make_response


def retrieve_player_by_name(fullname, location, ignoreunrated, strictnamechecking, dump="no"):

    #defining it to return it
    playerlist = []
    
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
        searchfirstname = fullnameaslist[0]
        searchlastname = fullnameaslist[-1]
    else:
        searchname = fullnameaslist
    
     # Returns a list of hits as ("fullname", UTR, "Location")
    utr_token = os.environ.get('UTR_TOKEN', '')
    if utr_token == '':
        # We'll check if there is a file in this same directory... 
        if os.path.isfile('UTR_TOKEN'):
            with open('UTR_TOKEN') as f:
                utr_token = f.read().rstrip("\n") #This 

    api_url = "https://agw-prod.myutr.com/v2/search/players"
    
    http = urllib3.PoolManager()

    if utr_token == "":
        response = http.request('GET', api_url, fields={"query":searchname})
    else:
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + utr_token
        }
        print ("Searching by name: " + searchname)
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
                if fullname.upper() != playerfullname.upper():
                    # We've tried to match the player's fullname as display name - problem found with Pratham Om Pathak!
                    if playerfirstname.upper() != searchfirstname.upper() or playerlastname.upper() != searchlastname.upper():
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

        if utr_token == "":
                playerrating = playerinfo["hits"][hit]["source"]["threeMonthRatingChangeDetails"]["ratingDisplay"]
        else:
                playerrating = playerinfo["hits"][hit]["source"]["singlesUtrDisplay"]
                #playerrating = playerinfo["hits"][hit]["source"]["myUtrSingles"]
        print(playerrating)
        if playerrating == None or playerrating == "0.00" or playerrating == "0.xx" or playerrating == 0.0 or playerrating == "Unrated":
            if ignoreunrated == "yes":
                continue
            else:
                playerrating = "0.00"

        playerratingfloat = float(playerrating)

        playerid = playerinfo["hits"][hit]["source"]["id"]

        if location == "":
            # location does not matter...
            playerlist.append((playername, playerlocation, playerratingfloat, playerinfo))
        else:
            if playerlocation.find(location) != -1:
                # If there is a location parameter match we add to the list, else ignore
                print("Adding player: " + str((playername, playerlocation, playerrating, playerid)))
                playerlist.append((playername, playerlocation, playerratingfloat, playerid))

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
    return render_template('searchoptions.html', header = "UTR Group Search options")

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
        if player == '':
            continue
        playerlist.extend(retrieve_player_by_name(player, location, ignoreunrated, strictnamechecking))

    # We reorder the list by UTR
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('presentresults.html', playerlist = playerlist, header = "Search Results", resultsheading = "The following players were found:")


#=======================================================================
# Search player list by URL
#=======================================================================
@app.route('/search_player_eventurl')
def present_search_player_by_url():
    return render_template('searchplayersbyeventurl.html')

@app.route('/search_player_eventurl_post', methods=['POST'])
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
        print(playerlink.get_text())
        playerlist.extend(retrieve_player_by_name(playerlink.get_text(), location, ignoreunrated, strictnamechecking))
    
    playerlist.sort(key=lambda x:x[2], reverse=True)    
    return render_template('presentresults.html', playerlist = playerlist, header = "Search Results", resultsheading = "EVENT: " + eventname)


#=======================================================================
# Print detailed info for a player
#=======================================================================
@app.route('/playerinfo')
def present_player_info():


    #print(type(parse_qs(request.args.get('playerinfo'))))
    #print(parse_qs(request.args.get('playerinfo')))
    #playerinfo = parse_qs(request.args.get('playerinfo'))
    #print(type(playerinfo))
  
    playerinfo=json.loads(parse_qs(request.args.get('playerinfo')))

    #   playerinfo = json.loads(response.data.decode("utf-8"))

    exit()
    
    playerinfo = parse_qs(request.args.get('playerinfo'))
    playerdisplayName = playerinfo["hits"]['0']["source"]["displayName"]
    playerthreeMonthRating= playerinfo["hits"][0]["source"]["threeMonthRating"]
    playermyUtrSinglesDisplay = playerinfo["hits"][0]["source"]["myUtrSinglesDisplay"]
    playerchangeDirection = playerinfo["hits"][0]["source"]["threeMonthRatingChangeDetails"]["changeDirection"]
 
    print(playerthreeMonthRating)
   
    return render_template('playerinfo.html')


#=======================================================================
# Dump JSON for single player
#=======================================================================
@app.route('/playerjson')
def present_json_player_form():
    return render_template('searchplayerbyjson.html')

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
