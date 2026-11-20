"""A local provider fixture verifies timestamps survive the actual streaming relay."""
import asyncio
import json
import unittest

from websockets.asyncio.server import serve
from voice_gateway import serve_voice, MODEL


class Socket:
    def __init__(self):
        self.messages=[]
        self.queue=asyncio.Queue()
        self.queue.put_nowait({'type':'websocket.receive','text':json.dumps({'type':'connect','key':'fixture-key'})})
        self.queue.put_nowait({'type':'websocket.receive','text':json.dumps({'type':'stop'})})

    async def receive(self):
        return await self.queue.get()

    async def send_json(self,data):
        self.messages.append(data)

    async def close(self):
        pass


class VoiceTimingGateway(unittest.IsolatedAsyncioTestCase):
    async def test_duration_limit_flushes_final_turn_and_terminates_provider(self):
        socket=Socket()
        # Continuous PCM must not indefinitely renew the recording's total duration.
        await socket.queue.get();await socket.queue.get()
        socket.queue.put_nowait({'type':'websocket.receive','text':json.dumps({'type':'connect','key':'fixture-key'})})
        async def audio():
            while True:
                socket.queue.put_nowait({'type':'websocket.receive','bytes':bytes(3200)})
                await asyncio.sleep(.005)
        commands=[]
        async def provider(connection):
            await connection.send(json.dumps({'type':'Begin','configuration':{'model':MODEL,'speaker_labels':True}}))
            async for raw in connection:
                if isinstance(raw,bytes): continue
                cmd=json.loads(raw)['type'];commands.append(cmd)
                if cmd=='ForceEndpoint':
                    await connection.send(json.dumps({'type':'Turn','turn_order':1,'end_of_turn':True,'speaker_label':'A','transcript':'Final words before the recording limit.'}))
                if cmd=='Terminate':
                    await connection.send(json.dumps({'type':'Termination'}));break
        commits=[];task=asyncio.create_task(audio())
        try:
            async with serve(provider,'127.0.0.1',0) as server:
                port=server.sockets[0].getsockname()[1]
                await asyncio.wait_for(serve_voice(socket,lambda *args:commits.append(args) or {},endpoint=f'ws://127.0.0.1:{port}',max_duration_seconds=.04),2)
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(commands,['ForceEndpoint','Terminate'])
        self.assertEqual(len(commits),1)
        self.assertEqual(socket.messages[-1]['reason'],'duration_limit')

    async def test_final_words_have_one_recording_id_and_duplicate_turns_are_ignored(self):
        event={'type':'Turn','turn_order':0,'end_of_turn':True,'speaker_label':'A','transcript':'Uniforms help families.',
               'words':[{'start':100,'end':500,'speaker':'A','word_is_final':True}]}
        async def provider(connection):
            await connection.send(json.dumps({'type':'Begin','configuration':{'model':MODEL,'speaker_labels':True}}))
            async for raw in connection:
                if json.loads(raw)['type']=='ForceEndpoint':
                    await connection.send(json.dumps(event))
                    await connection.send(json.dumps(event))
                else:
                    await connection.send(json.dumps({'type':'Termination'}))
                    break
        commits=[]
        def commit(speaker,text,timing):
            commits.append((speaker,text,timing))
            return {'id':'fixture'}
        socket=Socket()
        async with serve(provider,'127.0.0.1',0) as server:
            port=server.sockets[0].getsockname()[1]
            await serve_voice(socket,commit,endpoint=f'ws://127.0.0.1:{port}')
        self.assertEqual(len(commits),1)
        self.assertEqual(commits[0][2]['intervals'][0]['end_ms'],500)
        self.assertTrue(commits[0][2]['recording_id'])
        self.assertEqual(socket.messages[-1]['type'],'stopped')
        self.assertEqual(socket.messages[-1]['count'],1)


if __name__=='__main__':
    unittest.main()
