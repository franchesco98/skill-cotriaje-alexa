# -*- coding: utf-8 -*-

from email import header
from enum import Enum
import logging

import requests
import json
import datetime as dt

from ask_sdk_core.dispatch_components import (AbstractExceptionHandler,
                                              AbstractRequestHandler)
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model import Response

from ask_sdk_model.ui import SimpleCard

from ask_sdk_model.dialog import ElicitSlotDirective
from ask_sdk_model import (Intent, IntentConfirmationStatus, Slot, SlotConfirmationStatus)

from ask_sdk_model import (
    Response, IntentRequest, DialogState, SlotConfirmationStatus, Slot)

from .models import *

from datetime import date


sb = SkillBuilder()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def alexa_requests(tipo_peticion, url, auth_token = None, params = {}):
    bodyRequest = {
        "jsonrpc": "2.0",
        "params": params
    }

    header = {}

    if auth_token:
        header = {'Authorization': auth_token}

    if tipo_peticion == "GET":
        r = requests.get(url, json=bodyRequest, headers=header)
    elif tipo_peticion == "POST":
        r = requests.post(url, json=bodyRequest, headers=header)

    return r

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speech_text = "¡Bienvenido a triajes! Para iniciar sesión puedes decir, o bien 'inicia sesión', o simplemente 'soy', y tu nombre."

        handler_input.response_builder.speak(speech_text).set_should_end_session(False)

        return handler_input.response_builder.response

class CotriajeLoginIntentHandler(AbstractRequestHandler):
    def get_odoo_listatriajes(self, auth_token):
        return alexa_requests("GET", "http://localhost:8068/getSurveyByTriageId/1", auth_token)
    def can_handle(self, handler_input):
        return is_intent_name("CotriajeLogin")(handler_input)

    def handle(self, handler_input):
        datos_login = {
            "db": "MEET2CARE",
            "username": "admin",
            "password": "admin"
        }

        r = alexa_requests("POST", "http://localhost:8068/cotriajeLogin", params=datos_login)

        response_string = json.loads(r.text)
        token = response_string["result"]["cotriaje_token"]
        session_attributes = handler_input.attributes_manager.session_attributes

        session_attributes["cotriaje_token"] = token

        slots = handler_input.request_envelope.request.intent.slots
        nombre_usuario = slots['nombreUsuario']

        speech_text = "Ha iniciado sesión como {}".format(nombre_usuario.value)

        return TriajesPendientes.handle(self, handler_input,speech_text)

class TriajesPendientes(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return False

    def handle(self, handler_input, speech_text):
        session_attributes = handler_input.attributes_manager.session_attributes
        auth_token = session_attributes["cotriaje_token"]

        triajesPendientesRequest = alexa_requests("GET", "http://localhost:8068/getPendingTriagesByAuthenticatedUser", auth_token = auth_token)
        triajesPendientesResponse = json.loads(triajesPendientesRequest.text)
        print(triajesPendientesResponse)
        triajesPendientes= triajesPendientesResponse["result"]["response"]
        tamTriajesPendientes = len(triajesPendientes)
        print(tamTriajesPendientes)
        triajeDict = {}
        for t in triajesPendientes:
            triajeDict.setdefault(t["survey"][1], []).append({"id":t["id"],"maxDate":t["maxDate"]})
        session_attributes["triajeDict"]= triajeDict
        if len(triajesPendientes)== 0:
            speech_text += "No tiene triajes pendientes"
            handler_input.response_builder \
                .speak(speech_text) \
                .set_should_end_session(True)
            return handler_input.response_builder.response
        elif len(triajeDict)== 1:
            speech_text +=" Tienes un triaje pendiente de "+ list(triajeDict.keys())[0]+". Si desea realizarlo diga 'quiero realizarlo'. Si no quiere realizarlo diga 'salir'."
            session_attributes["empezarUnicoTriaje"]= True
            handler_input.response_builder \
                .speak(speech_text) \
                .set_should_end_session(False)
            return handler_input.response_builder.response
        else:
            listaClavesTriajes = list(triajeDict.keys())
            speech_text += "Tienes triajes de pendientes de {} y {}".format(", ".join(listaClavesTriajes[:-1]), listaClavesTriajes[-1])
            handler_input.response_builder \
                .speak(speech_text+"¿Cuál deseas realizar? Responde con 'quiero realizar el triaje' y el nombre del triaje que quiere realizar. Si no quiere realizar"
                     "ninguno diga 'salir'") \
                .set_should_end_session(False)
            return handler_input.response_builder.response


class EmpezarTriajeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("EmpezarTriajeIntent")(handler_input) \
               or is_intent_name("RealizarUnicoTriajeIntent")(handler_input)

    def get_odoo_triajes(self, auth_token, id):
        return alexa_requests("GET", "http://localhost:8068/getSurveyByTriageId/" + str(id), auth_token)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        intent_actual = handler_input.request_envelope.request.intent
        session_attributes = handler_input.attributes_manager.session_attributes
        auth_token = session_attributes["cotriaje_token"]
        session_attributes["triage_registry"] = []
        triajeDict = session_attributes["triajeDict"]
        if is_intent_name("RealizarUnicoTriajeIntent")(handler_input):
            triajesPendientes=next(iter(triajeDict.items()))[1]
        else:
            for clave,valor in triajeDict:
                if(slots["respuestaUsuario"].value in clave):
                    triajesPendientes = valor
                    break

        triajeARealizar = {}
        for triajePendiente in triajesPendientes:
            if(dt.datetime.strptime(triajePendiente["maxDate"], "%Y-%m-%d").date() >= dt.datetime.today().date()):
                triajeARealizar = triajePendiente
                break

        triaje_str = self.get_odoo_triajes(auth_token,triajeARealizar["id"]).text

        triaje = json.loads(triaje_str)

        triaje_result = triaje["result"]

        session_attributes["triaje_actual"] = triaje_result

        datos_triaje = triaje_result["response"][0]
        session_attributes["triage_actual_id"] = datos_triaje["surv_id"]
        bateria_preguntas_triaje = triaje_result["response"][1]

        # Creamos un diccionario que relacione las ids de las páginas de preguntas con su puntuación máxima
        bateria_preguntas_dict = {}
        for bateria_pregunta in bateria_preguntas_triaje:
            bateria_preguntas_dict[bateria_pregunta["page_id"]] = bateria_pregunta["page_max_score"]

        session_attributes["bateria_preguntas"] = bateria_preguntas_dict

        preguntas_triaje = {}

        for bloque_pregunta in bateria_preguntas_triaje:
            for pregunta in bloque_pregunta["page_ques"]:
                preguntas_triaje[pregunta["ques_id"]] = pregunta

        session_attributes["preguntas_triaje"] = preguntas_triaje

        primera_bateria_preguntas = bateria_preguntas_triaje[0]

        primera_pregunta = primera_bateria_preguntas["page_ques"][0]

        respuestas_primera_pregunta = primera_pregunta["ques_labs"][0]["lab_title"] + " o " \
                                      + primera_pregunta["ques_labs"][1]["lab_title"]

        session_attributes["puntuacion_actual"] = 0

        session_attributes["registry_pregunta_order"] = 0

        # Si la puntuación máxima es 0, guardaremos como valor -1.
        # Esto se debe a que hay páginas de preguntas con una o varias preguntas, cuya puntuación máxima es 0,
        # y las respuestas a las preguntas pueden ser excluyentes (se acaba el cuestionario con resultado POSITIVO)
        # o continuar el triaje
        puntuacion_maxima = primera_bateria_preguntas["page_max_score"]
        session_attributes["puntuacion_maxima"] = puntuacion_maxima if puntuacion_maxima > 0 else -1

        # A la hora de recitar las preguntas, Alexa consultará a una clase genérica, de modo que
        # necesitamos guardar cuál fue el id de la página de preguntas anterior para que,
        # al recitar una nueva pregunta, podamos saber si la pregunta que recitamos está en la misma
        # página o ha cambiado, para así poder tener control sobre la puntuación máxima.
        session_attributes["prev_pagina_preguntas_id"] = primera_bateria_preguntas["page_id"]
        session_attributes["prev_pregunta"] = primera_pregunta

        session_attributes["triaje_empezado"] = True

        speech_text = "Empezamos con el triaje. Primera pregunta. Responda solo {respuestas}: {pregunta}"\
            .format(respuestas=respuestas_primera_pregunta,
                    pregunta=primera_pregunta["ques_title"])

        handler_input.response_builder\
            .speak(speech_text)\
            .ask(primera_pregunta["ques_title"])\
            .set_should_end_session(False)

        return handler_input.response_builder.response


class TriajeRespuestaPregunta(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attributes = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.YesIntent")
                or is_intent_name("AMAZON.NoIntent")
                or is_intent_name("EmpezarTriajeIntent")
                or is_intent_name("TriajeRespuestaPregunta")) \
               and session_attributes["triaje_empezado"]

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        session_attributes = handler_input.attributes_manager.session_attributes
        intent_actual = handler_input.request_envelope.request.intent
        triage_registry = session_attributes["triage_registry"]

        pregunta_previa = session_attributes["prev_pregunta"]
        puntuacion_acumulada = session_attributes["puntuacion_actual"]
        es_respuesta_excluyente = False
        es_respuesta_terminante = False
        respuesta_siguiente_pregunta_id = False

        respuestas_dict = {}

        registry_pregunta_order = session_attributes["registry_pregunta_order"] + 1
        session_attributes["registry_pregunta_order"] = registry_pregunta_order

        triage_registry_pregunta = {
            "order": registry_pregunta_order,
            "question": pregunta_previa["ques_title"],
            "triage": session_attributes["triage_actual_id"]
        }

        if pregunta_previa["ques_type"] == "simple_choice":
            for pregunta_opcion in pregunta_previa["ques_labs"]:
                if pregunta_opcion["lab_title"].lower() == "sí" or pregunta_opcion["lab_title"].lower() == "si":
                    respuestas_dict["AMAZON.YesIntent"] = pregunta_opcion
                else:
                    respuestas_dict["AMAZON.NoIntent"] = pregunta_opcion
            print(respuestas_dict)

            respuesta_escogida = respuestas_dict[intent_actual.name]
            print(respuesta_escogida)
            triage_registry_pregunta["answer"] = respuesta_escogida["lab_title"]
            respuesta_siguiente_pregunta_id = respuesta_escogida["lab_next"]
            es_respuesta_excluyente = respuesta_escogida["lab_exclusive"]
            es_respuesta_terminante = respuesta_escogida["lab_finish"]
            puntuacion_acumulada += respuesta_escogida["lab_score"]
        else:
            respuesta_siguiente_pregunta_id = pregunta_previa["ques_next"]
            triage_registry_pregunta["answer"] = slots["respuestaUsuario"].value

        triage_registry.append(triage_registry_pregunta)
        session_attributes["triage_registry"] = triage_registry

        if session_attributes["puntuacion_maxima"] != puntuacion_acumulada:
            preguntas = session_attributes["preguntas_triaje"]

            if respuesta_siguiente_pregunta_id:
                siguiente_pregunta = preguntas[str(respuesta_siguiente_pregunta_id)]

                prev_bateria_preguntas_id = session_attributes["prev_pagina_preguntas_id"]
                if prev_bateria_preguntas_id != siguiente_pregunta["ques_page_id"]:
                    puntuacion_maxima = session_attributes["bateria_preguntas"][str(siguiente_pregunta["ques_page_id"])]
                    session_attributes["puntuacion_maxima"] = puntuacion_maxima if puntuacion_maxima > 0 else -1

                if siguiente_pregunta["ques_type"] == "simple_choice":
                    respuestas_siguiente_pregunta = siguiente_pregunta["ques_labs"][0]["lab_title"] + " o " \
                                                + siguiente_pregunta["ques_labs"][1]["lab_title"]
                    speech_text = "Siguiente pregunta. Responda solo {respuestas}: {pregunta}" \
                        .format(pregunta=siguiente_pregunta["ques_title"],
                                respuestas=respuestas_siguiente_pregunta)
                    handler_input.response_builder \
                        .speak(speech_text) \
                        .ask(siguiente_pregunta["ques_title"]) \
                        .set_should_end_session(False)
                else:
                    speech_text = siguiente_pregunta["ques_title"] + ". Responda de la siguiente forma: 'trabajo en', o 'trabajo de', y su profesión."
                    handler_input.response_builder \
                        .speak(speech_text) \
                        .set_should_end_session(False)

                session_attributes["prev_pagina_preguntas_id"] = siguiente_pregunta["ques_page_id"]
                session_attributes["prev_pregunta"] = siguiente_pregunta
                session_attributes["puntuacion_actual"] = puntuacion_acumulada

            elif es_respuesta_excluyente:
                speech_text = "Eres potencial positivo en COVID"

                triage_result = {
                    "triageResult": True,
                    "date": date.today().strftime('%d/m/%Y'),
                    "registry": triage_registry
                }

                r = alexa_requests("POST", "http://localhost:8068/updateTriageResult/"
                                   + str(session_attributes["triage_actual_id"]),
                                   auth_token=session_attributes["cotriaje_token"],
                                   params=triage_result)

                return TriajesPendientes.handle(self, handler_input, speech_text)
            else:
                speech_text = "Eres potencial negativo en COVID"

                triage_result = {
                    "triageResult": False,
                    "date": date.today().strftime('%d/m/%Y'),
                    "registry": triage_registry
                }

                r = alexa_requests("POST", "http://localhost:8068/updateTriageResult/"
                                   + str(session_attributes["triage_actual_id"]),
                                   auth_token=session_attributes["cotriaje_token"],
                                   params=triage_result)

                return TriajesPendientes.handle(self, handler_input, speech_text)
        else:
            speech_text = "Eres potencial positivo en COVID"

            triage_result = {
                "triageResult": True,
                "date": date.today().strftime('%d/m/%Y'),
                "registry": triage_registry
            }

            r = alexa_requests("POST", "http://localhost:8068/updateTriageResult/"
                               + str(session_attributes["triage_actual_id"]),
                               auth_token=session_attributes["cotriaje_token"],
                               params=triage_result)

            return TriajesPendientes.handle(self, handler_input, speech_text)

        return handler_input.response_builder.response
class HelloWorldIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("HelloWorldIntent")(handler_input)

    def handle(self, handler_input):
        speech_text = "¡Hola mundo en cotriaje Alexa!"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("Hello World", speech_text)
        ).set_should_end_session(True)
        
        return handler_input.response_builder.response

class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speech_text = "¡Puedes decirme hola!"
        
        handler_input.response_builder.speak(speech_text).ask(speech_text).set_card(
            SimpleCard("Hello World", speech_text)
        )

        return handler_input.response_builder.response

class CancelAndStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.CancelIntent")(handler_input) or is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        speech_text = "¡Adiós!"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("Hello World", speech_text)
        ).set_should_end_session(True)

        return handler_input.response_builder.response

class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        # any cleanup logic goes here

        return handler_input.response_builder.response

class AllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input: HandlerInput, exception: Exception):
        return True
    
    def handle(self, handler_input: HandlerInput, exception: Exception):
        print(exception)
        
        speech = "Lo siento, no te he entendido. ¿Puedes repetirlo?"

        handler_input.response_builder.speak(speech).ask(speech)

        return handler_input.response_builder.response

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(CotriajeLoginIntentHandler())
sb.add_request_handler(EmpezarTriajeIntentHandler())
sb.add_request_handler(TriajeRespuestaPregunta())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelAndStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(AllExceptionHandler())

handler = sb.lambda_handler()
