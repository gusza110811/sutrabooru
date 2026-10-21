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

    return result
}
