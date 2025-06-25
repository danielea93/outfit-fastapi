import json
import itertools
import random
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request

app = FastAPI()

# Carica dati da file
with open("config.json") as f:
    config = json.load(f)

with open("clothes_db.json") as f:
    clothes_db = json.load(f)

def get_current_temperature(location, api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&units=metric&appid={api_key}"
    response = requests.get(url)
    data = response.json()
    if response.status_code != 200:
        raise Exception(f"Errore API OpenWeather: {data.get('message', 'unknown error')}")
    return data["main"]["temp"]

def calculate_Wd(temp, Wd_rules):
    for rule in Wd_rules:
        if rule["min"] <= temp < rule["max"]:
            return rule["Wd"]
    if temp < Wd_rules[0]["min"]:
        return Wd_rules[0]["Wd"]
    if temp >= Wd_rules[-1]["max"]:
        return 0
    return 0

def format_outfits(outfits):
    result = []
    for idx, (outfit, Btot, Ctot, Wtot) in enumerate(outfits, start=1):
        groups = ["Layer 1", "Layer 2", "Pants", "Accessories", "Shoes"]
        formatted_items = []
        for i, group in enumerate(groups):
            name = outfit[i]["name"]
            if group == "Layer 2" and name.lower() == "nothing":
                continue
            formatted_items.append(name)
        outfit_str = ", ".join(formatted_items)
        result.append(outfit_str)
    return result

@app.get("/outfits")
def get_outfits():
    temp = get_current_temperature(config["location"], config["openweather_api_key"])
    Wd = calculate_Wd(temp, config["Wd_rules"])

    groups = ["Layer 1", "Layer 2", "Pants", "Accessories", "Shoes"]
    all_combinations = itertools.product(*(clothes_db[group] for group in groups))

    outfits_filtered = []
    for combo in all_combinations:
        Btot = sum(item["B"] for item in combo)
        if not (config["Bdmin"] <= Btot <= config["Bdmax"]):
            continue
        Ctot = sum(item["C"] for item in combo)
        if Ctot > config["Cd"]:
            continue
        Wtot = sum(item["W"] for item in combo)
        if Wtot != Wd:
            continue
        outfits_filtered.append(combo)

    outfits_with_totals = [
        (outfit, sum(i["B"] for i in outfit), sum(i["C"] for i in outfit), sum(i["W"] for i in outfit))
        for outfit in outfits_filtered
    ]

    formatted = format_outfits(outfits_with_totals)

    return JSONResponse(content={"temperature": temp, "Wd": Wd, "outfits": formatted})

@app.get("/")
def root():
    return {"message": "Server running, prova /outfits"}

@app.post("/alexa")
async def handle_alexa_request(request: Request):
    data = await request.json()

    try:
        intent_name = data["request"]["intent"]["name"]
    except KeyError:
        return JSONResponse(content={
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": "Mi dispiace, non ho capito la richiesta."
                },
                "shouldEndSession": True
            }
        })

    if intent_name == "GetOutfitsIntent":
        temp = get_current_temperature(config["location"], config["openweather_api_key"])
        Wd = calculate_Wd(temp, config["Wd_rules"])
        groups = ["Layer 1", "Layer 2", "Pants", "Accessories", "Shoes"]
        all_combinations = itertools.product(*(clothes_db[group] for group in groups))

        outfits_filtered = []
        for combo in all_combinations:
            Btot = sum(item["B"] for item in combo)
            if not (config["Bdmin"] <= Btot <= config["Bdmax"]):
                continue
            Ctot = sum(item["C"] for item in combo)
            if Ctot > config["Cd"]:
                continue
            Wtot = sum(item["W"] for item in combo)
            if Wtot != Wd:
                continue
            outfits_filtered.append(combo)

        if not outfits_filtered:
            speech_text = "Non ho trovato nessun outfit adatto per oggi."
        else:
            chosen_outfit = random.choice(outfits_filtered)
            parts = []
            for i, group in enumerate(groups):
                name = chosen_outfit[i]["name"]
                if group == "Layer 2" and name.lower() == "nothing":
                    continue
                parts.append(name)
            outfit_str = ", ".join(parts)
            speech_text = f"Ti consiglio di indossare: {outfit_str}."

        return JSONResponse(content={
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": speech_text
                },
                "shouldEndSession": True
            }
        })

    else:
        return JSONResponse(content={
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": "Intent non riconosciuto."
                },
                "shouldEndSession": True
            }
        })
