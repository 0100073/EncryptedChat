import tornado.ioloop
import tornado.web
import json

from Crypto.Cipher import AES
from Crypto import Random
from base64 import b64encode
from base64 import b64decode
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import random

import time
import urllib2
import json
from time import sleep

from threading import Thread

import base64

from ChatManager import ChatManager


class Constants:
    def __init__(self):
        pass

    COOKIE_NAME = "ChatCookie"


class JsonHandler(tornado.web.RequestHandler):
    """
    Request handler where requests and responses speak JSON.
    """

    def data_received(self, chunk):
        pass

    def __init__(self, application, request, **kwargs):
        super(JsonHandler, self).__init__(application, request, **kwargs)
        # Set up response dictionary.
        self.response = dict()

    def prepare(self):
        # Incorporate request JSON into arguments dictionary.
        if self.request.body:
            try:
                json_data = json.loads(self.request.body)
                self.request.arguments.update(json_data)
            except ValueError:
                message = 'Unable to parse JSON.'
                self.send_error(400, message=message)  # Bad Request

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kwargs):
        if 'message' not in kwargs:
            if status_code == 405:
                kwargs['message'] = 'Invalid HTTP method.'
            else:
                kwargs['message'] = 'Unknown error.'

        self.response = kwargs
        self.write_json()

    def write_json(self):
        output = json.dumps(self.response)
        self.write(output)

    def check_for_logged_in_user(self):
        user_name = self.get_secure_cookie(Constants.COOKIE_NAME)
        if not user_name:
            print "Unauthenticated request: denying answer!"
            self.send_error(401)  # Bad Request
        return user_name


class MainHandler(tornado.web.RequestHandler):

    def data_received(self, chunk):
        pass

    def get(self):
        """
        Not used URL entry.
        Only registered for convenience.
        """
        print "Main function, redirecting to login..."
        self.redirect("/login")

class LoginHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def post(self):
        """
        Try to login the user.
        Registered users are stored in RegisteredUsers.py
        Upon successful login, the user is added to the active users list.
        Further user authentication happens through cookies.
        """
        
        try:
            private_key = RSA.importKey(open("server_key.pem").read())
            cipher = PKCS1_OAEP.new(private_key)
        except Exception as e:
            self.send_error(400, message=e.message)
            return
        
        user_name = self.request.arguments['user_name']
        encrypted_password = self.request.arguments['password']
        
        encrypted_password_raw = base64.decodestring(encrypted_password)
        password = cipher.decrypt(encrypted_password_raw)
        
        encrypted_nonce_64 = self.request.arguments['nonce']
        encrypted_nonce = base64.decodestring(encrypted_nonce_64)
        nonce = cipher.decrypt(encrypted_nonce)
        
        encrypted_CMnonce_64 = self.request.arguments['cmnonce']
        encrypted_CMnonce = base64.decodestring(encrypted_CMnonce_64)
        cmnonce = cipher.decrypt(encrypted_CMnonce)
        
        current_user = cm.login_user(user_name, password)

        if current_user and cmnonce == cm.getNonce():
            cm.set_nonce()
            if not self.get_secure_cookie(Constants.COOKIE_NAME):
                self.set_secure_cookie(Constants.COOKIE_NAME, user_name)
            
            kfile = open(user_name.lower() + '-pubkey.pem')
            keystr = kfile.read()
            kfile.close()
            user_pubkey = RSA.importKey(keystr)
            reply_cipher = PKCS1_OAEP.new(user_pubkey)
            
            encrypted_reply_nonce = reply_cipher.encrypt(nonce)
            #print encrypted_reply_nonce
            encrypted_reply_nonce_64 = base64.encodestring(encrypted_reply_nonce)
            self.response = encrypted_reply_nonce_64
            self.write_json()
            
            print "User " + user_name + " successfully logged in!"
            self.set_status(200)
            self.finish()
        else:
            # authentication error
            self.set_status(401)
            self.finish()

class GetNonceHandler(JsonHandler):
    """
    Sends the client the current cm nonce
    """
    def data_received(self, chunk):
        pass
    
    def post(self):
        
        private_key = RSA.importKey(open("server_key.pem").read())
        cipher = PKCS1_OAEP.new(private_key)
        
        encrypted_user_name_64 = self.request.arguments['user_name']
        
        encrypted_user_name = base64.decodestring(encrypted_user_name_64)
        user_name = cipher.decrypt(encrypted_user_name)
        
        encrypted_nonce_64 = self.request.arguments['nonce']
        encrypted_nonce = base64.decodestring(encrypted_nonce_64)
        clnonce = cipher.decrypt(encrypted_nonce)
        
        try:
            cmnonce = cm.getNonce()
            kfile = open(user_name.lower() + '-pubkey.pem')
            keystr = kfile.read()
            kfile.close()
            user_pubkey = RSA.importKey(keystr)
            reply_cipher = PKCS1_OAEP.new(user_pubkey)
        except Exception as e:
            self.send_error(400, message=e.message)
            return
        
        encrypted_reply_cmnonce = reply_cipher.encrypt(cmnonce)
        encrypted_reply_cmnonce_64 = base64.encodestring(encrypted_reply_cmnonce)
        
        encrypted_reply_clnonce = reply_cipher.encrypt(clnonce)
        encrypted_reply_clnonce_64 = base64.encodestring(encrypted_reply_clnonce)
        
        #print clnonce, cmnonce
        self.response = {"clnonce": encrypted_reply_clnonce_64, "cmnonce": encrypted_reply_cmnonce_64}
        #two_nonces = [encrypted_reply_clnonce_64, encrypted_reply_cmnonce_64]
        #self.write_json(json.dumps(two_nonces))
        
         #= {"user_list":active_user_list, "user_info": participants_info}
        self.write_json()


class UsersHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def get(self):
        """
        Returns all registered user.
        Required for starting a new conversation.
        """

        print "Sending available users"
        users = cm.get_all_users()

        # Set JSON response
        self.response = users
        self.write_json()


class ConversationHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def get(self):
        """
        Returns all conversations for the logged in user.
        """

        # check user login
        user_name = self.check_for_logged_in_user()
        if not user_name:
            return

        print "Getting all conversations for user: " + user_name
        conversations = cm.get_my_conversations(user_name)
        user_conversations = []

        # transform the list of conversations
        for conversation in conversations:
            user_conversation = {'conversation_id': conversation.conversation_id,
                                 'participants': conversation.participants}
            user_conversations.append(user_conversation)

        self.write(json.dumps(user_conversations))


class ConversationCreateHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def post(self):
        """
        It creates a new conversation.
        Participant names are required in the json parameters.
        """

        # check user login
        user_name = self.check_for_logged_in_user()
        if not user_name:
            return

        try:
            # owner should be included as well!
            participants = self.request.arguments['participants']
            participants = json.loads(participants)
            cm.create_conversation(participants)
        except KeyError as e:
            print "KeyError during conversation creation!", e.message
            self.send_error(400, message=e.message)
            return
        except Exception as e:
            self.send_error(400, message=e.message)
            return

        self.set_status(200)
        self.finish()


class ConversationUserHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def get(self, conversation_id):
        conversation = cm.get_conversation(conversation_id)
        if not conversation:
            print "Conversation not found"
            self.send_error(500)
            return
        active_user_list = conversation.get_active_users_info()
        participants_info = conversation.get_users_info()
        print(active_user_list)
        print(participants_info)
        # send JSON reply
        self.response = {"user_list":active_user_list, "user_info": participants_info}
        self.write_json()


class ConcreteConversationHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    def get(self, conversation_id, last_message_id):
        """
        Sends back the messages since the last seen message for the client.
        :param conversation_id: the id of the conversation queried
        :param last_message_id: the id of the last message seen by the client
        :return: array of messages
        """

        # check user login
        user_name = self.check_for_logged_in_user()
        if not user_name:
            return

        print "Getting messages in conversation: " + str(conversation_id) + \
              " for user: " + user_name + \
              " since: " + str(last_message_id)

        conversation = cm.get_conversation(conversation_id)
        if not conversation:
            print "Conversation not found"
            self.send_error(500)
            return
        conversation.add_active_user(user_name)
        messages = conversation.get_messages_since(last_message_id)

        # Transforming the messages list for the chat client
        answer = []
        for message in messages:
            new_answer_item = dict()
            new_answer_item['content'] = message.content
            new_answer_item['message_id'] = message.message_id
            new_answer_item['owner'] = message.user_name
            answer.append(new_answer_item)

        # send JSON reply
        self.response = answer
        self.write_json()

    def post(self, conversation_id):
        """
        Process sent new messages.
        (Conversation id sent in URL parameter, message sent in POST body az JSON.
        :param conversation_id: the id of the conversation of the message
        """

        # check user login
        user_name = self.check_for_logged_in_user()
        if not user_name:
            return

        # getting the requested conversation
        conversation = cm.get_conversation(conversation_id)
        if not conversation:
            print "conversation not found"
            self.send_error(500)
            return

        # get the posted message
        try:
            # owner should be included as well!
            message = self.request.arguments['content']
            conversation.add_message(user_name, message)
        except KeyError as e:
            print "KeyError! Message content was not readable!", e.message
            self.send_error(400, message=e.message)
            return
        except Exception as e:
            print e.message
            self.send_error(400, message=e.message)
            return

        self.set_status(200)
        self.finish()


def init_app():
    """
    Initializes the Tornado web app.
    Registers the used URLs.
    """
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/getNonce", GetNonceHandler),
        (r"/users", UsersHandler),
        (r"/conversations", ConversationHandler),
        (r"/conversation_active_user/([0-9]+)", ConversationUserHandler),
        (r"/conversations/create", ConversationCreateHandler),
        (r"/conversations/([0-9]+)", ConcreteConversationHandler),
        (r"/conversations/([0-9]+)/([0-9]+)?", ConcreteConversationHandler)
    ],
        cookie_secret="6d41bbfe48ce3d078479feb364d98ecda2206edc"
    )


if __name__ == "__main__":
    cm = ChatManager()
    cm.set_nonce()
    app = init_app()
    print "Server Initialized"
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
