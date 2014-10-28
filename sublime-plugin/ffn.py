import httplib
import sublime
import sublime_plugin
import socket
import types
import threading
import time
import base64
import re
import HTMLParser

settings = None
def init():
    # initial FFN Plugin
    globals()['settings'] = sublime.load_settings('..\FFN\FFN.sublime-settings')

CHECK_DOWNLOAD_THREAD_TIME_MS = 1000
def monitorDownloadThread(downloadThread):
    if downloadThread.is_alive():
        msg = downloadThread.getCurrentMessage()
        sublime.status_message(msg)
        sublime.set_timeout(lambda: monitorDownloadThread(downloadThread), CHECK_DOWNLOAD_THREAD_TIME_MS)
    else:
        downloadThread.showResultToPresenter()

mRequest = {}
class DictionaryRequester(threading.Thread):

    REQUEST_TYPE_GET = "GET"
    REQUEST_TYPE_POST = "POST"
    REQUEST_TYPE_DELETE = "DELETE"
    REQUEST_TYPE_PUT = "PUT"

    httpRequestTypes = [REQUEST_TYPE_GET, REQUEST_TYPE_POST, REQUEST_TYPE_PUT, REQUEST_TYPE_DELETE]

    HTTP_URL = "http://"
    HTTPS_URL = "https://"

    httpProtocolTypes = [HTTP_URL, HTTPS_URL]

    HTTP_POST_BODY_START = "POST_BODY:"

    HTTP_PROXY_HEADER = "USE_PROXY"

    HTTPS_SSL_CLIENT_CERT = "CLIENT_SSL_CERT"
    HTTPS_SSL_CLIENT_KEY = "CLIENT_SSL_KEY"

    CONTENT_LENGTH_HEADER = "Content-lenght"

    MAX_BYTES_BUFFER_SIZE = 8192

    FILE_TYPE_HTML = "html"
    FILE_TYPE_JSON = "json"
    FILE_TYPE_XML = "xml"

    HTML_CHARSET_HEADER = "CHARSET"
    htmlCharset = "utf-8"

    httpContentTypes = [FILE_TYPE_HTML, FILE_TYPE_JSON, FILE_TYPE_XML]

    HTML_SHOW_RESULTS_SAME_FILE_HEADER = "SAME_FILE"
    showResultInSameFile = False

    DEFAULT_TIMEOUT = 30
    TIMEOUT_KEY = "TIMEOUT"

    def __init__(self, showTemplate):
        self.totalBytesDownloaded = 0
        self.contentLenght = 0
        self.showTemplate = showTemplate
        threading.Thread.__init__(self)

    def request(self, option):
        self.option = option
        self.start()
        sublime.set_timeout(lambda: monitorDownloadThread(self), CHECK_DOWNLOAD_THREAD_TIME_MS)

    def run(self):
        global mRequest
        FAKE_CURL_UA = "curl/7.21.0 (i486-pc-linux-gnu) libcurl/7.21.0 OpenSSL/0.9.8o zlib/1.2.3.4 libidn/1.15 libssh2/1.2.6"

        template = mRequest['template']
        auth = mRequest['auth']
        (host, port, request_page, requestType, httpProtocol) = self.extractRequestParams()

        print requestType, " ", httpProtocol, " HOST ", host, " PORT ", port, " PAGE: ", request_page

        extra_headers = {}
        proxyURL = ''
        requestPOSTBody = "keyword=%s&rootkeyword=%s&site=ffadult&lang=english&level=0&root=1&type=main&action=Load+local" % (mRequest['template'],mRequest['template'])
        timeoutValue = self.DEFAULT_TIMEOUT

        headers = {"User-Agent": FAKE_CURL_UA, "Accept": "*/*", "Authorization": auth}

        for key in extra_headers:
            headers[key] = extra_headers[key]

        # if valid POST body add Content-lenght header
        if len(requestPOSTBody) > 0:
            headers[self.CONTENT_LENGTH_HEADER] = len(requestPOSTBody)
            requestPOSTBody = requestPOSTBody.encode('utf-8')

        for key in headers:
            print "REQ HEADERS ", key, " : ", headers[key]

        respText = ""
        fileType = ""

        useProxy = False
        if len(proxyURL) > 0:
            useProxy = True

        # make http request
        try:
            if not(useProxy):
                if httpProtocol == self.HTTP_URL:
                    conn = httplib.HTTPConnection(host, port, timeout=timeoutValue)
                else:
                    if len(clientSSLCertificateFile) > 0 or len(clientSSLKeyFile) > 0:
                        print "Using client SSL certificate: ", clientSSLCertificateFile
                        print "Using client SSL key file: ", clientSSLKeyFile
                        conn = httplib.HTTPSConnection(
                            url, port, timeout=timeoutValue, cert_file=clientSSLCertificateFile, key_file=clientSSLKeyFile)
                    else:
                        conn = httplib.HTTPSConnection(url, port, timeout=timeoutValue)

                conn.request(requestType, request_page, requestPOSTBody, headers)
            else:
                print "Using proxy: ", proxyURL + ":" + str(proxyPort)
                conn = httplib.HTTPConnection(proxyURL, proxyPort, timeout=timeoutValue)
                conn.request(requestType, httpProtocol + url + request_page, requestPOSTBody, headers)

            startReqTime = time.time()
            resp = conn.getresponse()
            endReqTime = time.time()

            startDownloadTime = time.time()
            (respHeaderText, respBodyText, fileType) = self.getParsedResponse(resp)
            endDownloadTime = time.time()

            latencyTimeMilisec = int((endReqTime - startReqTime) * 1000)
            downloadTimeMilisec = int((endDownloadTime - startDownloadTime) * 1000)

            respText = self.getResponseTextForPresentation(respHeaderText, respBodyText, latencyTimeMilisec, downloadTimeMilisec)

            conn.close()
        except (socket.error, httplib.HTTPException, socket.timeout) as e:
            if not(isinstance(e, types.NoneType)):
                respText = "Error connecting: " + str(e)
            else:
                respText = "Error connecting"
        except AttributeError as e:
            print e
            respText = "HTTPS not supported by your Python version"

        self.respText = respText
        self.fileType = fileType

    def extractRequestParams(self):
        global mRequest

        requestType = self.REQUEST_TYPE_POST
        protocol    = mRequest['protocol']
        request_page= mRequest['page']
        host        = mRequest['host']

        if protocol == self.HTTP_URL:
            port = httplib.HTTP_PORT
        else:
            port = httplib.HTTPS_PORT

        if (mRequest['sandbox']):
            port = int(mRequest['sandbox'])

        # convert requested page to utf-8 and replace spaces with +
        request_page = request_page.encode('utf-8')
        request_page = request_page.replace(' ', '+')

        return (host, port, request_page, requestType, protocol)


    def getParsedResponse(self, resp):
        fileType = self.FILE_TYPE_HTML
        resp_status = "%d " % resp.status + resp.reason + "\n"
        respHeaderText = resp_status

        for header in resp.getheaders():
            respHeaderText += header[0] + ":" + header[1] + "\n"

            # get resp. file type (html, json and xml supported). fallback to html
            if header[0] == "content-type":
                fileType = self.getFileTypeFromContentType(header[1])

        respBodyText = ""
        self.contentLenght = int(resp.getheader("content-length", 0))

        # download a 8KB buffer at a time
        respBody = resp.read(self.MAX_BYTES_BUFFER_SIZE)
        numDownloaded = len(respBody)
        self.totalBytesDownloaded = numDownloaded
        while numDownloaded == self.MAX_BYTES_BUFFER_SIZE:
            data = resp.read(self.MAX_BYTES_BUFFER_SIZE)
            respBody += data
            numDownloaded = len(data)
            self.totalBytesDownloaded += numDownloaded

        respBodyText += respBody.decode(self.htmlCharset, "replace")

        return (respHeaderText, respBodyText, fileType)

    def getFileTypeFromContentType(self, contentType):
        fileType = self.FILE_TYPE_HTML
        contentType = contentType.lower()

        print "File type: ", contentType

        for cType in self.httpContentTypes:
            if cType in contentType:
                fileType = cType

        return fileType

    def getResponseTextForPresentation(self, respHeaderText, respBodyText, latencyTimeMilisec, downloadTimeMilisec):
        s = re.search(u'<textarea id=advedit name=data wrap=off rows=40 cols=135>([^<]+)</textarea>',respBodyText).group(1)
        h = HTMLParser.HTMLParser()
        return h.unescape(s)

    def getCurrentMessage(self):
        return "Downloading template: " + str(self.totalBytesDownloaded) + " / " + str(self.contentLenght)

    def showResultToPresenter(self):
        self.showTemplate.createWindowWithText(self.respText, self.fileType, self.showResultInSameFile)

class TemplatePresenter():

    def __init__(self):
        pass

    def createWindowWithText(self, textToDisplay, fileType, showResultInSameFile):
        if not(showResultInSameFile):
            view = sublime.active_window().new_file()
            openedNewView = True
        else:
            view = self.findHttpResponseView()
            openedNewView = False
            if view is None:
                view = sublime.active_window().new_file()
                openedNewView = True

        edit = view.begin_edit()
        if not(openedNewView):
            view.insert(edit, 0, "\n\n\n")
        view.insert(edit, 0, textToDisplay)
        view.end_edit(edit)
        view.set_scratch(True)
        view.set_read_only(False)
        view.set_name(mRequest['template'])
        view.set_syntax_file("Packages/HTML/HTML.tmLanguage")
        return view.id()

    def findHttpResponseView(self):
        for window in sublime.windows():
            for view in window.views():
                if view.name() == mRequest['template']:
                    return view

        return None

class FfnCommand(sublime_plugin.WindowCommand):
    TEMPLATE_TYPE_HTML = 'html'
    TEMPLATE_TYPE_JS   = 'javascript'
    TEMPLATE_TYPE_CSS  = 'css'
    TEMPLATE_TYPE_LESS = 'less'

    templateTypes = [TEMPLATE_TYPE_JS, TEMPLATE_TYPE_CSS, TEMPLATE_TYPE_LESS]

    def run(self):
        global mRequest, settings
        def on_done(str):
            mRequest['template'] = str
            key = str.split('-')[0]
            if (key in self.templateTypes):
                mRequest['type'] = key
            else:
                mRequest['type'] = self.TEMPLATE_TYPE_HTML

            # url
            server = settings.get('ffn_server','admin')
            if (server == 'admin'):
                mRequest['protocol'] = 'https://'
                mRequest['sandbox']  = ''
                mRequest['host']     = 'admin.friendfinderinc.com'
            else:
                mRequest['protocol'] = 'http://'
                mRequest['sandbox']  = settings.get('ffn_sandbox','')
                mRequest['host'] = server + '.friendfinderinc.com'

            mRequest['page'] = '/cgi-bin/admin/dictionary/editor.cgi'

            # request
            print 'start requesting....'
            showTemplate = TemplatePresenter()
            templateRequester = DictionaryRequester(showTemplate)

            option = {}
            templateRequester.request(option)

        def on_change(str):
            pass
        def on_cancel():
            pass

        auth = settings.get('ffn_auth')
        if (auth):
            mRequest['auth'] = auth
        else:
            sublime.status_message('Please Run Command: FFN SETUP first.')
            return
        template = ''
        if (template in mRequest):
            template = mRequest[template]
        self.window.show_input_panel('Template:', template, on_done, on_change, on_cancel)

class FfnSetupCommand(sublime_plugin.WindowCommand):
    keys = ['ffn_username',                   'ffn_auth',                   'ffn_server',                              'ffn_sandbox']
    desc = ['Please enter your FFN username', 'Please enter your password', 'Which server would you like to connect?', 'Please enter your sandbox number']
    current = 0
    def run(self):
        self.current = 0
        self.nextQuestion()
        return
    def done(self, value):
        key = self.keys[self.current]
        if key == 'ffn_auth':
            value = self.encodeAUTH(settings.get('ffn_username',''),value)
        settings.set(key, value)
        print settings.get(key,'')
        self.current += 1
        if len(self.keys) > self.current:
            self.nextQuestion()
        else:
            sublime.save_settings('..\FFN\FFN.sublime-settings')
    def nextQuestion(self):
        key = self.keys[self.current]
        question = self.desc[self.current]
        placeholder = ''
        if not(key == 'ffn_auth'):
            placeholder = settings.get(key, '')
        self.window.show_input_panel(question, placeholder, self.done, self.change, self.cancel)
        return
    def encodeAUTH(self, user, pw):
        return 'Basic ' + base64.standard_b64encode('%s:%s' % (user, pw))
    def change(a, b):
        pass
    def cancel():
        pass


init()

# FORM POST
'''
pickreview:skipreview
data: <<code>>
keyword:member_cell
rootkeyword:member_cell
site:ffadult
lang:english
level:0
root:1
type:
action:Load local
commitaction:
commmit_comment:
gittag:
'''
## pickreview : version#(537706) or [skipreview]
## action     : [Load local][Save local][Reload from DB][Publish][Commit to DB][Clear local]
## commit     : comment.match(/\bp?\d{5}\b/i) || comment.match(/\b\w+-\d+\b/) || comment.match(/\bp\d{5}[sb]\d+\b/i)  ==>  commit_comment = comment  &&  commitaction = 'Commit to DB'
