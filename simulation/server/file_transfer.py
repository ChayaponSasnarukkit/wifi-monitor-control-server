from fastapi import Depends, FastAPI, Request
from typing import List, Optional
import uvicorn, asyncio, string, random, time
from fastapi.responses import StreamingResponse, FileResponse
app = FastAPI()

def generate_random_string(length):
    # Get all the ASCII letters in lowercase and uppercase
    letters = string.ascii_letters
    # Randomly choose characters from letters for the given length of the string
    random_string = ''.join(random.choice(letters) for i in range(length))
    return random_string

# print("in progrees")
# all_chunks = [generate_random_string(64*1024) for i in range(2000) ]
@app.get("/downloadfile")
async def download_file(size: Optional[int]=1000000, chunk_size: Optional[int]=1024):
    def file_generator():
        try:
            total_sent = 0
            while total_sent < size:
                # print(total_sent)
                if size - total_sent < chunk_size:
                    yield generate_random_string(size - total_sent)
                else:
                    yield generate_random_string(chunk_size)
                total_sent += chunk_size
        except Exception:
            print("caught cancelled error")
            raise GeneratorExit
    try:
        return StreamingResponse(file_generator(), media_type="application/octet-stream")
    except Exception as e:
        print(str(e))
        exit()
    
@app.get("/downloadfilea")
async def download_filea(size: Optional[int]=1000000, chunk_size: Optional[int]=64*1024):
    async def file_generator():
        try:
            data = "a"*(chunk_size)
            total_sent = 0
            # print(total_sent)
            while total_sent < size:
                # print(total_sent)
                if total_sent == 0:
                    if size - total_sent < chunk_size:
                        packet_size = size - total_sent
                        if packet_size >= 18:
                            yield f"{time.time():.7f}{'a'*(packet_size-18)}"
                        else:
                            yield f"{time.time():.7f}"
                    else:
                        packet_size = chunk_size
                        yield f"{time.time():.7f}{data[:len(data)-18]}"
                else:
                    if size - total_sent < chunk_size:
                        packet_size = size - total_sent
                        yield "a"*packet_size
                    else:
                        packet_size = chunk_size
                        yield data
                # yield all_chunks[total_sent//chunk_size]
                # yield generate_random_string(packet_size)
                await asyncio.sleep(0.00001)
                total_sent += packet_size
            print(total_sent)
        except Exception:
            print("caught cancelled error")
            raise GeneratorExit
    try:
        return StreamingResponse(file_generator(), media_type="application/octet-stream")
    except Exception as e:
        print(str(e))
        exit()
        pass
if __name__ == "__main__":
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, workers=4, log_level="info")

    server = uvicorn.Server(config)
    server.run()