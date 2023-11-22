console.log("PostNL extension active");

chrome.webRequest.onBeforeRedirect.addListener(
    function(details) {
        if(details.redirectUrl.includes("postnl://login") === false) {
            return;
        }

        chrome.tabs.update({
            url: details.redirectUrl.replace(
                "postnl://login",
                "https://my.home-assistant.io/redirect/oauth"
                )
            });
    }, {urls: ["<all_urls>"]});