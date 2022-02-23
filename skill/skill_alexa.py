# -*- coding: utf-8 -*-

from email import header
from enum import Enum
import logging

import requests
import json

from ask_sdk_core.dispatch_components import (AbstractExceptionHandler,
                                              AbstractRequestHandler)
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model import Response
from ask_sdk_model.ui import SimpleCard

from ask_sdk_model.ui import SimpleCard
from ask_sdk_model import Response


from .models import *


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

    if tipo_peticion is "GET":
        r = requests.get(url, json=bodyRequest, headers=header)
    elif tipo_peticion is "POST":
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
    def can_handle(self, handler_input):
        return is_intent_name("CotriajeLogin")(handler_input)

    def handle(self, handler_input):
        datos_login = {
            "db": "MEET2CARE",
            "username": "admin",
            "password": "admin"
        }

        print("Antes de iniciar sesión")

        r = alexa_requests("POST", "http://localhost:8068/cotriajeLogin", params=datos_login)

        print("Después de iniciar sesión")

        response_string = json.loads(r.text)
        token = response_string["result"]["cotriaje_token"]
        session_attributes = handler_input.attributes_manager.session_attributes

        session_attributes["cotriaje_token"] = token

        slots = handler_input.request_envelope.request.intent.slots
        nombreUsuario = slots['nombreUsuario']

        speech_text = "Ha iniciado sesión como {}".format(nombreUsuario.value)

        # triajes = self.get_odoo_triajes(token)

        # if not triajes:
        #     speech_text += "Ahora mismo no dispone de triajes disponibles para realizar. Vuelva más tarde, por favor."
        # else:
        #     speech_text += "Tiene disponible para realizar los triajes "


        handler_input.response_builder.speak(speech_text).set_should_end_session(False)
        
        return handler_input.response_builder.response

class EmpezarTriajeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("EmpezarTriajeIntent")(handler_input)

    def get_odoo_triajes(self, auth_token):
        return alexa_requests("GET", "http://localhost:8068/getSurveyByTriageId/1", auth_token)

    def handle(self, handler_input):
        session_attributes = handler_input.attributes_manager.session_attributes
        auth_token = session_attributes["cotriaje_token"]
        
        triaje_str = self.get_odoo_triajes(auth_token).text

        triaje = json.loads(triaje_str)

        triaje_result = triaje["result"]

        session_attributes["triaje_actual"] = triaje_result

        datos_triaje = triaje_result["response"][0]
        bateria_preguntas_triaje = triaje_result["response"][1]

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
        session_attributes["puntuacion_maxima"] = primera_bateria_preguntas["page_max_score"]

        # A la hora de recitar las preguntas, Alexa consultará a una clase genérica, de modo que
        # necesitamos guardar cuál fue el id de la página de preguntas anterior para que,
        # al recitar una nueva pregunta, podamos saber si la pregunta que recitamos está en la misma
        # página o ha cambiado, para así poder tener control sobre la puntuación máxima.
        session_attributes["prev_pagina_preguntas"] = primera_bateria_preguntas
        session_attributes["prev_pregunta"] = primera_pregunta

        session_attributes["triaje_empezado"] = True

        speech_text = "Empezamos con el triaje. Primera pregunta. Responda solo {respuestas}: {pregunta}"\
            .format(pregunta=primera_pregunta["ques_title"],
                    respuestas=respuestas_primera_pregunta)

        handler_input.response_builder.speak(speech_text).set_should_end_session(False)

        return handler_input.response_builder.response


class TriajeRespuestaPregunta(AbstractRequestHandler):
    def can_handle(self, handler_input):
        session_attributes = handler_input.attributes_manager.session_attributes
        return is_intent_name("TriajeRespuestaPregunta") and session_attributes["triaje_empezado"]

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        session_attributes = handler_input.attributes_manager.session_attributes

        respuesta = slots["respuestaUsuario"]

        pregunta_previa = session_attributes["prev_pregunta"]
        puntuacion_acumulada = session_attributes["puntuacion_actual"]
        siguiente_pregunta = False

        if pregunta_previa.ques_type is "simple_choice":
            for opcion in pregunta_previa.ques_lab:
                if opcion.lab_title.lower() is "si" or opcion.lab_title.lower() is "no":
                    puntuacion_acumulada += opcion.lab_score
                    break
        else:
            pass

        pagina_previa = session_attributes["prev_pagina_preguntas"]

        speech_text = "Eres potencial positivo en COVID."

        if pagina_previa.page_max_score != puntuacion_acumulada:
            preguntas = session_attributes["preguntas_triaje"]

            if pregunta_previa.lab_next:
                siguiente_pregunta = preguntas[pregunta_previa.lab_next]

                respuestas_siguiente_pregunta = " o ".join(filter(None, [", ".join(siguiente_pregunta.ques_labs[:-1])]
                                                                + siguiente_pregunta.ques_labs[-1:]))
                speech_text = "Siguiente pregunta. Responda solo {respuestas}: {pregunta}" \
                    .format(pregunta=siguiente_pregunta.ques_title,
                            respuestas=respuestas_siguiente_pregunta)

            handler_input.response_builder.speak(speech_text).set_should_end_session(False)

            return handler_input.response_builder.response

        handler_input.response_builder.speak(speech_text).set_should_end_session(False)

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
