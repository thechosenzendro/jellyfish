const syncSocket = new WebSocket("ws://localhost:8000/sync")

syncSocket.onopen = (event) => {
    console.log("Connected to the sync socket")
    document.dispatchEvent(new Event("syncConnected"))
}

syncSocket.on = (action, cb) => {
    const old_onmessage = syncSocket.onmessage
    console.log(old_onmessage)
    syncSocket.onmessage = async (event) => {
        const data = JSON.parse(event.data)
        console.log(`Got some data! Is this right?: ${event.data}`)
        if (data.action == action) {
            await cb(data)
        }
        else {
            old_onmessage(data)
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

document.addEventListener("healthcheck", async () => {
    console.log("Healthcheck!")
    const healthcheck_result = await (await fetch("/healthcheck")).json()
    if (healthcheck_result.trade_node_check == true, healthcheck_result.broker_api_check == true) {
        document.getElementById("healthcheck_icon").setAttribute("fill", "#008000")
    }
})
document.addEventListener("onbeforeunload", () => {
    document.removeEventListener("healthcheck")
    document.removeEventListener("onbeforeunload")
})
setInterval(() => { document.dispatchEvent(new Event("healthcheck")) }, 1000)