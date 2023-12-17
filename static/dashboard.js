const syncSocket = new WebSocket("ws://localhost:8000/sync")

syncSocket.onopen = (event) => {
    console.log("Connected to the sync socket")
    document.dispatchEvent(new Event("syncConnected"))
}

syncSocket.on = (action, cb) => {
    syncSocket.onmessage = async (event) => {
        const data = JSON.parse(event.data)
        console.log(`Got some data! Is this right?: ${event.data}`)
        if (data.action == action) {
            await cb(data)
        }
    }
}

syncSocket.get = (request) => {
    return new Promise((resolve, reject) => {
        syncSocket.send(JSON.stringify(request))
        syncSocket.onerror = (err) => {
            console.log(`An error happened during the GET operation: ${err}`)
            reject(err)
        }
        syncSocket.onmessage = (event) => {
            console.log(`Got data!: ${event.data}`)
            resolve(event.data)
        }
    })
}

