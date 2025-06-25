from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import itertools
import requests

# La tua app FastAPI deve essere definita prima dei decoratori
app = FastAPI()

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
        response = {
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": speech_text
                },
                "shouldEndSession": False
            }
        }
        print("Risposta Alexa:", json.dumps(response, indent=2))
        return JSONResponse(content=response)

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

                if not formatted:
                    speech_text = "Purtroppo non ho trovato outfit adatti per te in questo momento."
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

                # Creo lista per APL
                items = [{"primaryText": o} for o in formatted]

                apl_document = {
                    "type": "APL",
                    "version": "1.7",
                    "mainTemplate": {
                        "parameters": ["payload"],
                        "items": [
                            {
                                "type": "Container",
                                "padding": 20,
                                "items": [
                                    {
                                        "type": "Text",
                                        "text": f"Temperatura: {round(temp)}°C - Outfit consigliati",
                                        "style": "textStylePrimary",
                                        "height": "30dp",
                                        "width": "100%"
                                    },
                                    {
                                        "type": "Sequence",
                                        "scrollDirection": "vertical",
                                        "data": "${payload.items}",
                                        "height": "100%",
                                        "width": "100%",
                                        "item": {
                                            "type": "Text",
                                            "text": "${data.primaryText}",
                                            "style": "textStyleBody",
                                            "paddingTop": 10,
                                            "paddingBottom": 10
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }

                response = {
                    "version": "1.0",
                    "response": {
                        "directives": [
                            {
                                "type": "Alexa.Presentation.APL.RenderDocument",
                                "token": "outfitToken",
                                "document": apl_document,
                                "datasources": {
                                    "payload": {
                                        "items": items
                                    }
                                }
                            }
                        ],
                        "shouldEndSession": True,
                        "outputSpeech": {
                            "type": "PlainText",
                            "text": "Ecco gli outfit consigliati."
                        }
                    }
                }
                print("Risposta Alexa con APL:", json.dumps(response, indent=2))
                return JSONResponse(content=response)

            except Exception as e:
                speech_text = f"Si è verificato un errore: {str(e)}"
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
                print("Errore Alexa:", json.dumps(response, indent=2))
                return JSONResponse(content=response)

        else:
            speech_text = "Mi dispiace, non ho capito la tua richiesta."
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
