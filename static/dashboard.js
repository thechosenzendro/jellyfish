class SyncSocket {
    constructor(url) {
        this.connect = (url) => {
            this.socket = new WebSocket(url)

            this.socket.onopen = (event) => {
                console.log("Connected to the sync socket")
                document.dispatchEvent(new Event("syncConnected"))
            }

            this.socket.onmessage = (event) => {
                const dispatchEvent = new CustomEvent("sync_message", { detail: JSON.parse(event.data) })
                document.dispatchEvent(dispatchEvent)
            }

            this.socket.onclose = (event) => {
                console.error("Disconnected from the sync socket")
                setInterval(() => {
                    if (this.socket.readyState == this.socket.CLOSED) {
                        console.warn("Trying to reconnect to the sync socket")
                        this.connect(this.WS_URL)
                    }
                }, 500)
            }

        }
        this.WS_URL = url
        this.connect(this.WS_URL)
    }

    on(action, cb) {
        async function onHandler(event) {
            const data = event.detail
            if (action == data.action) {
                await cb(data)
            }
        }
        document.addEventListener("sync_message", onHandler)
    }

    get(request) {
        this.socket.send(JSON.stringify(request))
        return new Promise((resolve, reject) => {
            function getHandler(event) {
                const data = event.detail
                if (request.action == data.action) {
                    document.removeEventListener("sync_message", getHandler)
                    resolve(data)
                }
            }

            document.addEventListener("sync_message", getHandler)
        })
    }

}

const WS_URL = "ws://localhost:8000/sync"
let syncSocket = new SyncSocket(WS_URL)

document.addEventListener("healthcheck", async () => {
    function markAsPassed(elementId) {
        const element = document.getElementById(elementId)
        element.setAttribute("class", "green_text")
        element.innerHTML = "OK"
    }

    function markAsFailed(elementId, message) {
        const element = document.getElementById(elementId)
        element.setAttribute("class", "alert_text")
        element.innerHTML = `Error: ${message}`
    }


    console.log("Healthcheck!")
    const icon = document.getElementById("healthcheck_icon")
    try {
        const healthcheck_result = await (await fetch("/healthcheck")).json()
        markAsPassed("server_check")
        if (healthcheck_result.trade_node_check == true) {
            markAsPassed("trade_node_check")
            icon.setAttribute("fill", "#008000")
        }
        else {
            markAsFailed("trade_node_check", "Server se nemůže připojit k obchodním uzlům.")
            icon.setAttribute("fill", " #FF0000")
        }

        if (healthcheck_result.broker_api_check == true) {
            markAsPassed("broker_api_check")
            icon.setAttribute("fill", "#008000")
        }
        else {
            markAsFailed("broker_api_check", "Server se nemůže připojit k API brokera.")
            icon.setAttribute("fill", " #FF0000")
        }

    } catch {
        markAsFailed("server_check", "Nelze se připojit k serveru.")
        markAsFailed("trade_node_check", "Nelze ověřit kvůli předchozí chybě.")
        markAsFailed("broker_api_check", "Nelze ověřit kvůli předchozí chybě.")
        icon.setAttribute("fill", " #FF0000")
    }

})
document.addEventListener("onbeforeunload", () => {
    document.removeEventListener("healthcheck")
    document.removeEventListener("onbeforeunload")
})
setInterval(() => { document.dispatchEvent(new Event("healthcheck")) }, 1000)

async function toggleGeneral(btn) {
    const label = btn.getElementsByClassName("center")[0]
    if (label.innerHTML == "STOP") {
        if (confirm("Opravdu chcete zastavit obchodování?")) {
            const result = await syncSocket.get({ action: "stop_trading" })
            if (result.data.result == "ok") {
                btn.setAttribute("class", "green btn center")
                label.innerHTML = "START"
            }
            else {
                alert(`Error: ${JSON.stringify(result)}`)
            }

        }
    }
    else {
        const result = await syncSocket.get({ action: "start_trading" })
        if (result.data.result == "ok") {
            btn.setAttribute("class", "alert btn center")
            label.innerHTML = "STOP"
        }
        else {
            alert(`Error: ${result}`)
        }


    }
}