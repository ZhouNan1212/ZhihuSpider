# -*- coding: utf-8 -*-

import logging
import telnetlib
import random
import redis
import json
import os
import threading
import pdb
from scrapy import signals
from .user_agents_pc import agents
from .proxy import initIPPOOLS, removeIPPOOLS
from .cookie import initCookie, updateCookie, removeCookie
from scrapy.utils.response import response_status_message
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import IgnoreRequest

# ------------------------------------------
#   版本：1.0
#   日期：2017-8-06
#   作者：AlexTan
#   <CSDN:   http://blog.csdn.net/alextan_>  
#   <e-mail: alextanbz@gmail.com>
# ------------------------------------------

logger = logging.getLogger(__name__)

class UserAgentMiddleware(object):
    """ 换User-Agent """

    def process_request(self, request, spider):
        agent = random.choice(agents)
        request.headers["User-Agent"] = agent

class ProxyMiddleware(RetryMiddleware):
    '''IP代理'''
    def __init__(self, settings, crawler):
        #自己获取的ip
        self.TIMES = 10
        RetryMiddleware.__init__(self, settings)
        self.rconn = settings.get("RCONN", redis.Redis(crawler.settings.get('REDIS_HOST', 'localhsot'), crawler.settings.get('REDIS_PORT', 6379)))
        #initIPPOOLS(self.rconn)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    def process_request(self,request,spider):
        #pdb.set_trace()
        ipNum=len(self.rconn.keys('IP*'))
        if ipNum<20:
            proxy_thread = threading.Thread(target= initIPPOOLS,args = (self.rconn,))
            proxy_thread.setDaemon(True)
            proxy_thread.start()
            #initIPPOOLS(self.rconn)
        if self.TIMES >= 3:
            baseIP=random.choice(self.rconn.keys('IP:*'))
            ip=str(baseIP,'utf-8').replace('IP:','')
            try:
                IP=ip.split(':')[0]
                PORT=ip.split(':')[1]
                telnetlib.Telnet(IP,port=PORT,timeout=2) #测试ip是否可以用
            except:
                removeIPPOOLS(self.rconn,ip)
            else:
                #pdb.set_trace()
                self.IP = "http://" + ip
                print("当前使用的代理IP是："+self.IP)
                self.TIMES = 0
                #pdb.set_trace()
        else:
            self.TIMES += 1
        if self.IP is not '':
            request.meta["proxy"] = self.IP
            #pdb.set_trace()

    def process_response(self,request,response,spider):
        #pdb.set_trace()
        if response.status in [400,403,404,429,500,503,504]:
            self.IP = 10
            logger.error("%s! 错误..." % response.status)
            #pdb.set_trace()
            try:
                removeIPPOOLS(self.rconn,request.meta['proxy'].replace('http://',''))
            except:
                pass
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response  # 重试
        else:
            return response

    def process_exception(self, request, exception, spider):
        #pdb.set_trace()
        self.IP = 10
        try:
            removeIPPOOLS(self.rconn,request.meta['proxy'].replace('http://',''))
        except:
            pass
        return request
        #pdb.set_trace()


class CookiesMiddleware(RetryMiddleware):
    """ 维护Cookie """

    def __init__(self, settings, crawler):
        RetryMiddleware.__init__(self, settings)
        self.rconn = settings.get("RCONN", redis.Redis(crawler.settings.get('REDIS_HOST', 'localhsot'), crawler.settings.get('REDIS_PORT', 6379)))
        initCookie(self.rconn, crawler.spider.name)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    def process_request(self, request, spider):
        redisKeys = self.rconn.keys()
        while len(redisKeys) > 0:
            elem = random.choice(redisKeys)
            #pdb.set_trace()
            if b'zhihuspider:Cookies' in elem:
                #pdb.set_trace()
                elem = str(elem,'utf-8')
                cookie = json.loads(str(self.rconn.get(elem),'utf-8'))
                request.cookies = cookie
                request.meta["accountText"] = elem.split("Cookies:")[-1]
                break
            else:
                #pdb.set_trace()
                redisKeys.remove(elem)

    def process_response(self, request, response, spider):
        #pdb.set_trace()
        reason = response_status_message(response.status)
        if response.status in [300, 301, 302, 303]:
            pdb.set_trace()
            if reason == '301 Moved Permanently':
                return self._retry(request, reason, spider) or response  # 重试
            else:
                raise IgnoreRequest
        elif response.status in [403, 414]:
            logger.error("%s! Stopping..." % response.status)
            os.system("pause")
            updateCookie(request.meta['accountText'], self.rconn, spider.name, request.cookies)
            return self._retry(request, reason, spider) or response  # 重试
        else:
            return response
