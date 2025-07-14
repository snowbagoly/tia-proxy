# TIA proxy server

This project was created as a Proof-of-Concept to replace the [Chrome plugin](https://github.com/cqse/teamscale-ados-test-listener) with a custom proxy.

# Usage

1. Download and install [mitmproxy](https://mitmproxy.org/).
2. Set the environment variable `COMMANDER_SERVER_URL` to use the REST service of the Commander Server, e.g. `set COMMANDER_SERVER_URL=http://localhost:5000`
3. Start mitmproxy with the script provided in this repository: `mitmproxy -s run_proxy.py`
4. Start the browser with the proxy, e.g. `"Google Chrome.lnk" --proxy-server="http://192.168.178.42:8080" --proxy-bypass-list="127.0.0.1;localhost" --user-data-dir=C:\Temp\user-data-dir  --no-first-run`
5. When using the proxy for the first time, you have to install its certificate to be able to access HTTPS:
    - Open http://mitm.it in the browser that you started up with the proxy settings.
    - Download the corresponding certificate.
    - Click on "Show Instructions" and follow the steps to install the certificate.
6. Now you should be able to open your Azure DevOps in the browser that you started up with the proxy settings, and when a test is started, a corresponding log message should appear in the running Commander Server.


# Troubleshooting options

While you are running the proxy server, it shows all requests that it registers in the console.

The custom script logs each request that it intercepts in the same folder where it is started from.

The Commander Server logs each request that it registers in the console.

# TODOs left

- Currently the request calls are insecure.
- The Chrome plugin detected when the test window was closed, and closed the running test accordingly. Can we capture this via the proxy?