const updateEvent = new Event("update")
setInterval(() => {
    document.dispatchEvent(updateEvent)
}, 1000)