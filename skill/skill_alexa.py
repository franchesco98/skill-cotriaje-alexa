# -*- coding: utf-8 -*-

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

sb = SkillBuilder()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def alexa_requests(tipo_peticion, url, auth_token = None, params = {}):
    bodyRequest = {
        "jsonrpc": "2.0",
        "params": params
    }

    if tipo_peticion is "GET":
        r = requests.get(url, json=bodyRequest)
    elif tipo_peticion is "POST":
        r = requests.post(url, json=bodyRequest)

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

        r = alexa_requests("POST", "http://localhost:8068/cotriajeLogin", params=datos_login)

        response_string = json.loads(r.text)
        token = response_string["result"]["cotriaje_token"]

        slots = handler_input.request_envelope.request.intent.slots
        nombreUsuario = slots['nombreUsuario']

        speech_text = "Ha iniciado sesión como {}".format(nombreUsuario.value)

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
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelAndStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(AllExceptionHandler())

handler = sb.lambda_handler()
