export function getCookie(name) {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        cookie = cookie.trim();
        // Check if this cookie string begins with the name we want
        if (cookie.startsWith(name + '=')) {
        return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    return null; // Return null if the cookie wasn't found
}

export function setCookie(name, value, daysToLive) {
    let cookieString = encodeURIComponent(name) + "=" + encodeURIComponent(value);
    
    if (daysToLive !== undefined) {
        const date = new Date();
        // Convert days to milliseconds
        date.setTime(date.getTime() + (daysToLive * 24 * 60 * 60 * 1000));
        cookieString += "; expires=" + date.toUTCString();
    }
    
    // path=/ makes the cookie available across the entire website
    // SameSite=Lax protects against cross-site request forgery (CSRF)
    cookieString += "; path=/; SameSite=Lax";
    
    document.cookie = cookieString;
}

export function timeAgo(timestamp) {
    // Ensure timestamp is in milliseconds (multiply by 1000 if it's in seconds)
    const diffMs = Date.now() - timestamp;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSec < 60) return 'Just now';
    if (diffMin < 60) return `${diffMin} min${diffMin === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hr${diffHours === 1 ? '' : 's'} ago`;
    if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
    
    return new Date(timestamp).toLocaleDateString();
}

export async function postMsg(thread, author, body) {
    let payload = {
        "thread": thread,
        "author": author,
        "body": body
    }
    console.log(payload)
    let result = await fetch("/api/m", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    })

    const data = await result.json().catch(() => ({}));
    return { ok: result.ok, data: data};
}

export async function postThread(board, title) {
    let payload = {
        "board": board,
        "title": title
    }
    console.log(payload)
    let result = await fetch("/api/t", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    })

    const data = await result.json().catch(() => ({}));
    return { ok: result.ok, data: data};
}

export async function sendNotification(title, body, tag) {
    // 1. Check if the browser supports notifications
    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notifications.");
        return;
    }

    if (Notification.permission === "default") {
        await Notification.requestPermission()
    }

    // 2. Check if permission is already granted
    if (Notification.permission === "granted") {
        // Create and display the notification
        const notification = new Notification(title, {
            body: body,
            icon: "/favicon.ico",
            tag: tag
        });

        // Optional: Add a click event to focus the window or redirect
        notification.onclick = function () {
            window.focus();
            this.close(); // Closes the notification window
        };
    }
}
