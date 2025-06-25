import json
import itertools
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
        outfit_str = f"{idx}. " + ", ".join(formatted_items) + f" (B={Btot}, C={Ctot}, W={Wtot})"
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

@app.post("/alexa")
async def handle_alexa_request(request: Request):
    body = await request.json()
    print("Richiesta da Alexa:", json.dumps(body, indent=2))

    request_type = body.get("request", {}).get("type")

    if request_type == "LaunchRequest":
        speech_text = (
            "Benvenuto nella skill Mostra Outfit! "
            "Puoi chiedermi di consigliarti un outfit dicendo, per esempio, mostrami un outfit."
        )
    
    elif request_type == "IntentRequest":
        intent = body.get("request", {}).get("intent", {}).get("name")
        if intent == "GetOutfitIntent":
            try:
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
                speech_text = (
                    f"La temperatura attuale è di {round(temp)} gradi. "
                    + (f"Ti consiglio: {formatted[0]}" if formatted else "Purtroppo non ho trovato outfit adatti.")
                )
            except Exception as e:
                speech_text = f"Si è verificato un errore: {str(e)}"
        else:
            speech_text = "Mi dispiace, non ho capito la tua richiesta."
    else:
        speech_text = "Mi dispiace, tipo di richiesta non supportato."

    response = {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech_text
            },
            "shouldEndSession": True
        }
    }
    print("Risposta Alexa:", json.dumps(response, indent=2))
    return JSONResponse(content=response)

@app.get("/")
def root():
    return {"message": "Server running, prova /outfits"}
