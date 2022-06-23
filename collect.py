import os
import time
import json
import socket
import asyncio
import threading

_BLEAK='_BLEAK'
_READ='_READ'
# _SOCKET='_SOCKET'

MODE=_BLEAK
DEBUG=True

if MODE==_BLEAK:
    from bleak import BleakClient

def pt(s:str,flush:bool=False)->None:
    if flush or DEBUG:
        print(s,flush=True)


cfg=json.load(open(os.path.join(os.path.dirname(__file__),'collect.json'),'rb'))
alpha=cfg['alpha']
devices=[cfg[i] for i in cfg['collect']]
ADDR=('0.0.0.0',cfg['port'])
KEY=open(os.path.join(os.path.dirname(__file__),'collect.key'),'rb').read()

cache={}
cache_flag={i:False for i in devices}


def f(addr:str,data:bytes)->None:
    assert len(data)==20
    (ox55,ox61,axL,axH,ayL,ayH,azL,azH,wxL,wxH,wyL,wyH,wzL,wzH,RollL,RollH,PitchL,PitchH,YawL,YawH)=data
    assert ox55==0x55
    assert ox61==0x61

    def int2(h:int,l:int)->int:
        ans=(h<<8)|l
        if ans>32767:
            ans-=65536
        return ans

    ax=int2(axH,axL)
    ay=int2(ayH,ayL)
    az=int2(azH,azL)
    wx=int2(wxH,wxL)
    wy=int2(wyH,wyL)
    wz=int2(wzH,wzL)
    Roll=int2(RollH,RollL)
    Pitch=int2(PitchH,PitchL)
    Yaw=int2(YawH,YawL)

    def linear(x:int,k:int)->float:
        return k*x/32768

    ax=linear(ax,16)
    ay=linear(ay,16)
    az=linear(az,16)
    wx=linear(wx,2000)
    wy=linear(wy,2000)
    wz=linear(wz,2000)
    Roll=linear(Roll,180)
    Pitch=linear(Pitch,180)
    Yaw=linear(Yaw,180)

    agx=ax
    agy=ay
    agz=az
    alx=0
    aly=0
    alz=0

    if addr in cache:
        (lax,lay,laz,lwx,lwy,lwz,lRoll,lPitch,lYaw,lalx,laly,lalz,lagx,lagy,lagz)=cache[addr]
        agx=alpha*lagx+(1-alpha)*ax
        agy=alpha*lagy+(1-alpha)*ay
        agz=alpha*lagz+(1-alpha)*az
        alx=ax-agx
        aly=ay-agy
        alz=az-agz

    cache[addr]=(ax,ay,az,wx,wy,wz,Roll,Pitch,Yaw,alx,aly,alz,agx,agy,agz)
    cache_flag[addr]=True



def notification_handler(devid):
    def handler(sender,data):
        f(devid,data)
    return handler

async def run(devid):
    _count=0
    while True:
        try:
            pt('BConnect: %s'%(devid,))
            client = BleakClient(devid)
            await client.connect()
            await client.start_notify(cfg['imuReadUUID'], notification_handler(devid))
            _count=0
        except:
            _count+=1
            if _count>=10:
                pt('BFailed: %s'%(devid,))
                # sys.exit(0)
                OFFLINE=True
                return

async def main():
    tasks=[run(i) for i in devices]
    await asyncio.gather(*tasks)


CSV=os.path.join(os.path.dirname(__file__),'collect.csv')
data=list()
for i in open(CSV,'r').read().split('\n'):
    i=i.split(',')
    data.append(','.join(i[0:30]+i[75:90]).encode('utf8'))
n=len(data)
i=-1


def getmsg()->bytes:
    global MODE,i
    while not all(cache_flag.values()):
        if MODE!=_BLEAK:
            break
        time.sleep(0.01)
    if MODE==_READ:
        i=(i+1)%n
        return data[i]
    ans=''
    for i in devices:
        ans+=','.join([str(j) for j in cache[i]])
        ans+='' if i is devices[-1] else ','
        cache_flag[i]=False
    return ans.encode('utf8')


con=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
con.bind(ADDR)
con.listen(1)

def mian()->None:
    while True:
        ss,caddr=con.accept()
        pt('SConnect: %s'%(caddr,))
        while True:
            rd=ss.recv(1024)
            if rd!=KEY:
                break
            ss.send(getmsg())
        ss.close()
        pt('SClose: %s'%(caddr,))


threading.Thread(target=mian,daemon=True).start()
threading.Thread(target=mian,daemon=True).start()
if MODE==_BLEAK:
    try:
        asyncio.run(main())
    except:
        pt('BFailed: main')
        MODE=_READ
else:
    while True:
        time.sleep(1000)
