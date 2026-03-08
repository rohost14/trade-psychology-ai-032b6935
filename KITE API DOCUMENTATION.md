KITE API DOCUMENTATION:\
\
Introduction¶

Kite Connect is a set of REST-like HTTP APIs that expose many
capabilities required to build a complete stock market investment and
trading platform. It lets you execute orders in real time (equities,
commodities, mutual funds), manage user portfolios, stream live market
data over WebSockets, and more.

Kite Connect

All inputs are form-encoded parameters and responses are JSON (apart
from a couple exceptions). The responses may be Gzipped. Standard HTTP
codes are used to indicate success and error states with accompanying
JSON data. The API endpoints are not cross site request enabled, hence
cannot be called directly from browsers.

An api_key + api_secret pair is issued and you have to register a
redirect url where a user is sent after the login flow. For mobile and
desktop applications, there has to be a remote backend which does the
handshake on behalf of the mobile app and the api_secret should never be
embedded in the app.

Getting Started & Prerequisites¶

To use Kite Connect APIs, you\'ll need:

Trading Account Requirements¶

An active Zerodha trading account.

Account with 2FA TOTP enabled.

Developer Account Setup¶

Create Developer Account: Visit the Kite Connect Developer Portal and
sign up.

App Creation: Log in and create a new app to get your API credentials.

Set Redirect URL: Configure the URL where user will be redirected after
authentication.

Get API Keys: Note down your api_key and api_secret (keep the secret
secure) for future reference.

Start Building¶

Once you have your API credentials:

Complete Authentication: Follow the login flow documentation to
authenticate user.

Choose Your SDK: Pick from our official libraries in your preferred
language.

Explore Examples & Documentation: Each SDK comes with comprehensive
examples and documentation to help you get started quickly.

Note

The authentication flow is crucial for security - make sure to
understand it thoroughly before proceeding.\
\
\
\
Response structure¶

All GET and DELETE request parameters go as query parameters, and POST
and PUT parameters as form-encoded (application/x-www-form-urlencoded)
parameters, responses from the API are always JSON.

Successful request¶

HTTP/1.1 200 OK

Content-Type: application/json

{

\"status\": \"success\",

\"data\": {}

}

All responses from the API server are JSON with the content-type
application/json unless explicitly stated otherwise. A successful 200 OK
response always has a JSON response body with a status key with the
value success. The data key contains the full response payload.

Failed request¶

HTTP/1.1 500 Server error

Content-Type: application/json

{

\"status\": \"error\",

\"message\": \"Error message\",

\"error_type\": \"GeneralException\"

}

A failure response is preceded by the corresponding 40x or 50x HTTP
header. The status key in the response envelope contains the value
error. The message key contains a textual description of the error and
error_type contains the name of the exception. There may be an optional
data key with additional payload.

Data types¶

Values in JSON responses are of types string, int, float, or bool.

Timestamp (datetime) strings in the responses are represented in the
form yyyy-mm-dd hh:mm:ss, set under the Indian timezone (IST) ---
UTC+5.5 hours.

A date string is represented in the form yyyy-mm-dd\
\
\
Exceptions and errors¶

In addition to the 40x and 50x headers, error responses come with the
name of the exception generated internally by the API server. You can
define corresponding exceptions in your language or library, and raise
them by doing a switch on the returned exception name.

Example¶

HTTP/1.1 500 Server error

Content-Type: application/json

{

\"status\": \"error\",

\"message\": \"Error message\",

\"error_type\": \"GeneralException\"

}

exception

TokenException Preceded by a 403 header, this indicates the expiry or
invalidation of an authenticated session. This can be caused by the user
logging out, a natural expiry, or the user logging into another Kite
instance. When you encounter this error, you should clear the user\'s
session and re-initiate a login.

UserException Represents user account related errors

OrderException Represents order related errors such placement failures,
a corrupt fetch etc

InputException Represents missing required fields, bad values for
parameters etc.

MarginException Represents insufficient funds, required for the order
placement

HoldingException Represents insufficient holdings, available to place
sell order for specified instrument

NetworkException Represents a network error where the API was unable to
communicate with the OMS (Order Management System)

DataException Represents an internal system error where the API was
unable to understand the response from the OMS to inturn respond to a
request

GeneralException Represents an unclassified error. This should only
happen rarely

Common HTTP error codes¶

code

400 Missing or bad request parameters or values

403 Session expired or invalidate. Must relogin

404 Request resource was not found

405 Request method (GET, POST etc.) is not allowed on the requested
endpoint

410 The requested resource is gone permanently

429 Too many requests to the API (rate limiting)

500 Something unexpected went wrong

502 The backend OMS is down and the API is unable to communicate with it

503 Service unavailable; the API is down

504 Gateway timeout; the API is unreachable

API rate limit¶

end-point rate-limit

Quote 1req/second

Historical candle 3req/second

Order placement 10req/second

All other endpoints 10req/second\
\
\
\
User¶

Login flow¶

The login flow starts by navigating to the public Kite login endpoint.

https://kite.zerodha.com/connect/login?v=3&api_key=xxx

A successful login comes back with a request_token as a URL query
parameter to the redirect URL registered on the developer console for
that api_key. This request_token, along with a checksum (SHA-256 of
api_key + request_token + api_secret) is POSTed to the token API to
obtain an access_token, which is then used for signing all subsequent
requests. In summary:

Navigate to the Kite Connect login page with the api_key

A successful login comes back with a request_token to the registered
redirect URL

POST the request_token and checksum (SHA-256 of api_key +
request_token + api_secret) to /session/token

Obtain the access_token and use that with all subsequent requests

An optional redirect_params param can be appended to public Kite login
endpoint, that will be sent back to the redirect URL. The value is URL
encoded query params string, eg: some=X&more=Y). eg:
https://kite.zerodha.com/connect/login?v=3&api_key=xxx&redirect_params=some%3DX%26more%3DY

Here\'s a webinar that shows the login flow and other interactions.

Kite Connect handshake flow

Warning

Never expose your api_secret by embedding it in a mobile app or a client
side application. Do not expose the access_token you obtain for a
session to the public either.

type endpoint

POST /session/token Authenticate and obtain the access_token after the
login flow

GET /user/profile Retrieve the user profile

GET /user/margins/:segment Retrieve detailed funds and margin
information

DELETE /session/token Logout and invalidate the API session and
access_token

Authentication and token exchange¶

Once the request_token is obtained from the login flow, it should be
POSTed to /session/token to complete the token exchange and retrieve the
access_token.

curl https://api.kite.trade/session/token \\

-H \"X-Kite-Version: 3\" \\

-d \"api_key=xxx\" \\

-d \"request_token=yyy\" \\

-d \"checksum=zzz\"

{

\"status\": \"success\",

\"data\": {

\"user_type\": \"individual\",

\"email\": \"XXXXXX\",

\"user_name\": \"Kite Connect\",

\"user_shortname\": \"Connect\",

\"broker\": \"ZERODHA\",

\"exchanges\": \[

\"NSE\",

\"NFO\",

\"BFO\",

\"CDS\",

\"BSE\",

\"MCX\",

\"BCD\",

\"MF\"

\],

\"products\": \[

\"CNC\",

\"NRML\",

\"MIS\",

\"BO\",

\"CO\"

\],

\"order_types\": \[

\"MARKET\",

\"LIMIT\",

\"SL\",

\"SL-M\"

\],

\"avatar_url\": \"abc\",

\"user_id\": \"XX0000\",

\"api_key\": \"XXXXXX\",

\"access_token\": \"XXXXXX\",

\"public_token\": \"XXXXXXXX\",

\"enctoken\": \"XXXXXX\",

\"refresh_token\": \'\',

\"silo\": \'\',

\"login_time\": \"2021-01-01 16:15:14\",

\"meta\": {

\"demat_consent\": \"physical\"

}

}

}

Request parameters¶

parameter

api_key The public API key

request_token The one-time token obtained after the login flow. This
token\'s lifetime is only a few minutes and it is meant to be exchanged
for an access_token immediately after being obtained

checksum SHA-256 hash of (api_key + request_token + api_secret)

Response attributes¶

attribute

user_id

string

The unique, permanent user id registered with the broker and the
exchanges

user_name

string

User\'s real name

user_shortname

string

Shortened version of the user\'s real name

email

string

User\'s email

user_type

string

User\'s registered role at the broker. This will be individual for all
retail users

broker

string

The broker ID

exchanges

string\[\]

Exchanges enabled for trading on the user\'s account

products

string\[\]

Margin product types enabled for the user

order_types

string\[\]

Order types enabled for the user

api_key

string

The API key for which the authentication was performed

access_token

string

The authentication token that\'s used with every subsequent request
Unless this is invalidated using the API, or invalidated by a
master-logout from the Kite Web trading terminal, it\'ll expire at 6 AM
on the next day (regulatory requirement)

public_token

string

A token for public session validation where requests may be exposed to
the public

refresh_token

string

A token for getting long standing read permissions. This is only
available to certain approved platforms

login_time

string

User\'s last login time

meta

map

demat_consent: empty, consent or physical

avatar_url

string

Full URL to the user\'s avatar (PNG image) if there\'s one

Signing requests¶

Once the authentication is complete, all requests should be signed with
the HTTP Authorization header with token as the authorisation scheme,
followed by a space, and then the api_key:access_token combination. For
example:

curl -H \"Authorization: token api_key:access_token\"

curl -H \"Authorization: token xxx:yyy\"

User profile¶

While a successful token exchange returns the full user profile, it\'s
possible to retrieve it any point of time with the /user/profile API. Do
note that the profile API does not return any of the tokens.

curl https://api.kite.trade/user/profile \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": {

\"user_id\": \"AB1234\",

\"user_type\": \"individual\",

\"email\": \"xxxyyy@gmail.com\",

\"user_name\": \"AxAx Bxx\",

\"user_shortname\": \"AxAx\",

\"broker\": \"ZERODHA\",

\"exchanges\": \[

\"BFO\",

\"MCX\",

\"NSE\",

\"CDS\",

\"BSE\",

\"BCD\",

\"MF\",

\"NFO\"

\],

\"products\": \[

\"CNC\",

\"NRML\",

\"MIS\",

\"BO\",

\"CO\"

\],

\"order_types\": \[

\"MARKET\",

\"LIMIT\",

\"SL\",

\"SL-M\"

\],

\"avatar_url\": null,

\"meta\": {

\"demat_consent\": \"physical\"

}

}

}

Response attributes¶

attribute

user_id

string

The unique, permanent user id registered with the broker and the
exchanges

user_name

string

User\'s real name

user_shortname

string

Shortened version of the user\'s real name

email

string

User\'s email

user_type

string

User\'s registered role at the broker. This will be individual for all
retail users

broker

string

The broker ID

exchanges

string\[\]

Exchanges enabled for trading on the user\'s account

products

string\[\]

Margin product types enabled for the user

order_types

string\[\]

Order types enabled for the user

meta

map

demat_consent: empty, consent or physical

avatar_url

string

Full URL to the user\'s avatar (PNG image) if there\'s one

Funds and margins¶

A GET request to /user/margins returns funds, cash, and margin
information for the user for equity and commodity segments.

A GET request to /user/margins/:segment returns funds, cash, and margin
information for the user. segment in the URI can be either equity or
commodity.

curl \"https://api.kite.trade/user/margins\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": {

\"equity\": {

\"enabled\": true,

\"net\": 99725.05000000002,

\"available\": {

\"adhoc_margin\": 0,

\"cash\": 245431.6,

\"opening_balance\": 245431.6,

\"live_balance\": 99725.05000000002,

\"collateral\": 0,

\"intraday_payin\": 0

},

\"utilised\": {

\"debits\": 145706.55,

\"exposure\": 38981.25,

\"m2m_realised\": 761.7,

\"m2m_unrealised\": 0,

\"option_premium\": 0,

\"payout\": 0,

\"span\": 101989,

\"holding_sales\": 0,

\"turnover\": 0,

\"liquid_collateral\": 0,

\"stock_collateral\": 0,

\"delivery\": 0

}

},

\"commodity\": {

\"enabled\": true,

\"net\": 100661.7,

\"available\": {

\"adhoc_margin\": 0,

\"cash\": 100661.7,

\"opening_balance\": 100661.7,

\"live_balance\": 100661.7,

\"collateral\": 0,

\"intraday_payin\": 0

},

\"utilised\": {

\"debits\": 0,

\"exposure\": 0,

\"m2m_realised\": 0,

\"m2m_unrealised\": 0,

\"option_premium\": 0,

\"payout\": 0,

\"span\": 0,

\"holding_sales\": 0,

\"turnover\": 0,

\"liquid_collateral\": 0,

\"stock_collateral\": 0,

\"delivery\": 0

}

}

}

}

Response attributes¶

attribute

enabled

bool

Indicates whether the segment is enabled for the user

net

float64

Net cash balance available for trading (intraday_payin + adhoc_margin +
collateral)

available.cash

float64

Raw cash balance in the account available for trading (also includes
intraday_payin)

available.opening_balance

float64

Opening balance at the day start

available.live_balance

float64

Current available balance

available.intraday_payin

float64

Amount that was deposited during the day

available.adhoc_margin

float64

Additional margin provided by the broker

available.collateral

float64

Margin derived from pledged stocks

utilised.m2m_unrealised

float64

Un-booked (open) intraday profits and losses

utilised.m2m_realised

float64

Booked intraday profits and losses

utilised.debits

float64

Sum of all utilised margins (unrealised M2M + realised M2M + SPAN +
Exposure + Premium + Holding sales)

utilised.span

float64

SPAN margin blocked for all open F&O positions

utilised.option_premium

float64

Value of options premium received by shorting

utilised.holding_sales

float64

Value of holdings sold during the day

utilised.exposure

float64

Exposure margin blocked for all open F&O positions

utilised.liquid_collateral

float64

Margin utilised against pledged liquidbees ETFs and liquid mutual funds

utilised.delivery

float64

Margin blocked when you sell securities (20% of the value of stocks
sold) from your demat or T1 holdings

utilised.stock_collateral

float64

Margin utilised against pledged stocks/ETFs

utilised.turnover

float64

Utilised portion of the maximum turnover limit (only applicable to
certain clients)

utilised.payout

float64

Funds paid out or withdrawn to bank account during the day

Logout¶

This call invalidates the access_token and destroys the API session.
After this, the user should be sent through a new login flow before
further interactions. This does not log the user out of the official
Kite web or mobile applications.

curl \--request DELETE \\

-H \"X-Kite-Version: 3\" \\

\"https://api.kite.trade/session/token?api_key=xxx&access_token=yyy\"

{

\"status\": \"success\",

\"data\": true

}\
\
\
Orders¶

The order APIs let you place orders of different varities, modify and
cancel pending orders, retrieve the daily order and more.

type endpoint

POST /orders/:variety Place an order of a particular variety

PUT /orders/:variety/:order_id Modify an open or pending order

DELETE /orders/:variety/:order_id Cancel an open or pending order

GET /orders Retrieve the list of all orders (open and executed) for the
day

GET /orders/:order_id Retrieve the history of a given order

GET /trades Retrieve the list of all executed trades for the day

GET /orders/:order_id/trades Retrieve the trades generated by an order

Glossary of constants¶

Here are several of the constant enum values used for placing orders.

param values

variety regular Regular order

amo After Market Order

co Cover Order ?

iceberg Iceberg Order ?

auction Auction Order ?

order_type MARKET Market order

LIMIT Limit order

SL Stoploss order ?

SL-M Stoploss-market order ?

product CNC Cash & Carry for equity ?

NRML Normal for futures and options ?

MIS Margin Intraday Squareoff for futures and options ?

MTF Margin Trading Facility ?

validity DAY Regular order

IOC Immediate or Cancel

TTL Order validity in minutes

market_protection 0 No market protection (default)

0 - 100 Custom market protection percentage (e.g., 2 for 2% protection,
10 for 10% protection)

-1 Automatic market protection applied by the system as per market
protection guidelines

autoslice true Enable automatic order slicing for quantities above
freeze limits ?

false Disable automatic order slicing (default)

Placing orders¶

Placing an order implies registering it with the OMS via the API. This
does not guarantee the order\'s receipt at the exchange. The fate of an
order is dependent on several factors including market hours,
availability of funds, risk checks and so on. Under normal
circumstances, order placement, receipt by the OMS, transport to the
exchange, execution, and the confirmation roundtrip happen instantly.

When an order is successfully placed, the API returns an order_id. The
status of the order is not known at the moment of placing because of the
aforementioned reasons.

In case of non-MARKET orders that may be open indefinitely during the
course of a trading day, it is not practical to poll the order APIs
continuously to know the status. For this, postbacks are ideal as they
sent order updates asynchronously as they happen.

Note

Successful placement of an order via the API does not imply its
successful execution. To know the true status of a placed order, you
should scan the order history or retrieve the particular order\'s
current details using its order_id.

Order varieties¶

You can place orders of different varieties---regular orders, after
market orders, cover orders, iceberg orders etc. See the list of
varieties here.

curl https://api.kite.trade/orders/regular \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\" \\

-d \"tradingsymbol=ACC\" \\

-d \"exchange=NSE\" \\

-d \"transaction_type=BUY\" \\

-d \"order_type=MARKET\" \\

-d \"quantity=1\" \\

-d \"product=MIS\" \\

-d \"validity=DAY\"

{

\"status\": \"success\",

\"data\": {

\"order_id\": \"151220000000000\"

}

}

Regular order parameters¶

These parameters are common across different order varieties.

parameter

tradingsymbol Tradingsymbol of the instrument ?

exchange Name of the exchange (NSE, BSE, NFO, CDS, BCD, MCX)

transaction_type BUY or SELL

order_type Order type (MARKET, LIMIT etc.)

quantity Quantity to transact

product Margin product to use for the order (margins are blocked based
on this) ?

price The price to execute the order at (for LIMIT orders)

trigger_price The price at which an order should be triggered (SL, SL-M)

disclosed_quantity Quantity to disclose publicly (for equity trades)

validity Order validity (DAY, IOC and TTL)

validity_ttl Order life span in minutes for TTL validity orders

iceberg_legs Total number of legs for iceberg order type (number of legs
per Iceberg should be between 2 and 10)

iceberg_quantity Split quantity for each iceberg leg order
(quantity/iceberg_legs)

auction_number

string

A unique identifier for a particular auction

market_protection Market protection percentage for MARKET and SL-M
orders. Values: 0 (no protection), 0-100 (custom %), -1 (auto
protection)

autoslice Enable automatic slicing for orders exceeding freeze quantity
limits. Values: true (enable), false (disable, default) ?

tag An optional tag to apply to an order to identify it (alphanumeric,
max 20 chars)

Modifying orders¶

As long as on order is open or pending in the system, certain attributes
of it may be modified. It is important to sent the right value for
:variety in the URL.

curl \--request PUT
https://api.kite.trade/orders/regular/151220000000000 \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\" \\

-d \"order_type=MARKET\" \\

-d \"quantity=3\" \\

-d \"validity=DAY\"

{

\"status\": \"success\",

\"data\": {

\"order_id\": \"151220000000000\"

}

}

Regular order parameters¶

parameter

order_type

quantity

price

trigger_price

disclosed_quantity

validity

Cover order (CO) parameters¶

parameter

order_id Unique order ID

price The price to execute the order at

trigger_price For LIMIT Cover orders

Cancelling orders¶

As long as on order is open or pending in the system, it can be
cancelled.

curl \--request DELETE \\

\"https://api.kite.trade/orders/regular/151220000000000\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\" \\

{

\"status\": \"success\",

\"data\": {

\"order_id\": \"151220000000000\"

}

}

Retrieving orders¶

The order history or the order book is transient as it only lives for a
day in the system. When you retrieve orders, you get all the orders for
the day including open, pending, and executed ones.

curl \"https://api.kite.trade/orders\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": \[

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"100000000000000\",

\"exchange_order_id\": \"200000000000000\",

\"parent_order_id\": null,

\"status\": \"CANCELLED\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2021-05-31 09:18:57\",

\"exchange_update_timestamp\": \"2021-05-31 09:18:58\",

\"exchange_timestamp\": \"2021-05-31 09:15:38\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"CDS\",

\"tradingsymbol\": \"USDINR21JUNFUT\",

\"instrument_token\": 412675,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"product\": \"NRML\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 72,

\"trigger_price\": 0,

\"average_price\": 0,

\"filled_quantity\": 0,

\"pending_quantity\": 1,

\"cancelled_quantity\": 1,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": \"XXXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"300000000000000\",

\"exchange_order_id\": \"400000000000000\",

\"parent_order_id\": null,

\"status\": \"COMPLETE\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2021-05-31 15:20:28\",

\"exchange_update_timestamp\": \"2021-05-31 15:20:28\",

\"exchange_timestamp\": \"2021-05-31 15:20:28\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"NSE\",

\"tradingsymbol\": \"IOC\",

\"instrument_token\": 415745,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"product\": \"CNC\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 109.4,

\"trigger_price\": 0,

\"average_price\": 109.4,

\"filled_quantity\": 1,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": \"XXXXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"500000000000000\",

\"exchange_order_id\": \"600000000000000\",

\"parent_order_id\": null,

\"status\": \"COMPLETE\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2021-05-31 15:20:51\",

\"exchange_update_timestamp\": \"2021-05-31 15:20:52\",

\"exchange_timestamp\": \"2021-05-31 15:20:52\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"NSE\",

\"tradingsymbol\": \"IOC\",

\"instrument_token\": 415745,

\"order_type\": \"MARKET\",

\"transaction_type\": \"SELL\",

\"validity\": \"DAY\",

\"product\": \"CNC\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 0,

\"trigger_price\": 0,

\"average_price\": 109.35,

\"filled_quantity\": 1,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": \"XXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"220524001859672\",

\"exchange_order_id\": null,

\"parent_order_id\": null,

\"status\": \"REJECTED\",

\"status_message\": \"Insufficient funds. Required margin is 95417.84
but available margin is 74251.80. Check the orderbook for open
orders.\",

\"status_message_raw\": \"RMS:Margin Exceeds,Required:95417.84,
Available:74251.80 for entity account-XXXXX across exchange across
segment across product \",

\"order_timestamp\": \"2022-05-24 12:26:52\",

\"exchange_update_timestamp\": null,

\"exchange_timestamp\": null,

\"variety\": \"iceberg\",

\"modified\": false,

\"exchange\": \"NSE\",

\"tradingsymbol\": \"SBIN\",

\"instrument_token\": 779521,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"TTL\",

\"validity_ttl\": 2,

\"product\": \"CNC\",

\"quantity\": 200,

\"disclosed_quantity\": 0,

\"price\": 463,

\"trigger_price\": 0,

\"average_price\": 0,

\"filled_quantity\": 0,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {

\"iceberg\": {

\"leg\": 1,

\"legs\": 5,

\"leg_quantity\": 200,

\"total_quantity\": 1000,

\"remaining_quantity\": 800

}

},

\"tag\": \"icebergord\",

\"tags\": \[

\"icebergord\"

\],

\"guid\": \"XXXXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"700000000000000\",

\"exchange_order_id\": \"800000000000000\",

\"parent_order_id\": null,

\"status\": \"COMPLETE\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2021-05-31 16:00:36\",

\"exchange_update_timestamp\": \"2021-05-31 16:00:36\",

\"exchange_timestamp\": \"2021-05-31 16:00:36\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL21JUNFUT\",

\"instrument_token\": 58424839,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"product\": \"NRML\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 4854,

\"trigger_price\": 0,

\"average_price\": 4852,

\"filled_quantity\": 1,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": \"connect test order1\",

\"tags\": \[

\"connect test order1\"

\],

\"guid\": \"XXXXXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"9000000000000000\",

\"exchange_order_id\": \"1000000000000000\",

\"parent_order_id\": null,

\"status\": \"COMPLETE\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2021-05-31 16:08:40\",

\"exchange_update_timestamp\": \"2021-05-31 16:08:41\",

\"exchange_timestamp\": \"2021-05-31 16:08:41\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL21JUNFUT\",

\"instrument_token\": 58424839,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"product\": \"NRML\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 4854,

\"trigger_price\": 0,

\"average_price\": 4852,

\"filled_quantity\": 1,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": \"connect test order2\",

\"tags\": \[

\"connect test order2\",

\"XXXXX\"

\],

\"guid\": \"XXXXXX\"

},

{

\"placed_by\": \"XXXXXX\",

\"order_id\": \"98000000000000000\",

\"exchange_order_id\": \"67000000000000000\",

\"parent_order_id\": null,

\"status\": \"CANCELLED\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2023-06-12 14:00:58\",

\"exchange_update_timestamp\": \"2023-06-12 14:00:58\",

\"exchange_timestamp\": \"2023-06-12 14:00:58\",

\"variety\": \"auction\",

\"modified\": false,

\"exchange\": \"NSE\",

\"tradingsymbol\": \"BHEL\",

\"instrument_token\": 112129,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"SELL\",

\"validity\": \"DAY\",

\"validity_ttl\": 0,

\"product\": \"CNC\",

\"quantity\": 60,

\"disclosed_quantity\": 0,

\"price\": 85,

\"trigger_price\": 0,

\"auction_number\": \"22\",

\"average_price\": 0,

\"filled_quantity\": 0,

\"pending_quantity\": 60,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": null

},

{

\"account_id\": \"XXXXXX\",

\"placed_by\": \"XXXXXX\",

\"order_id\": \"250117800776785\",

\"exchange_order_id\": \"1300000029561105\",

\"parent_order_id\": null,

\"status\": \"CANCELLED\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2025-01-17 11:49:45\",

\"exchange_update_timestamp\": \"2025-01-17 11:49:45\",

\"exchange_timestamp\": \"2025-01-17 11:49:45\",

\"variety\": \"regular\",

\"modified\": false,

\"exchange\": \"NSE\",

\"tradingsymbol\": \"SBIN\",

\"instrument_token\": 779521,

\"order_type\": \"LIMIT\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"validity_ttl\": 0,

\"product\": \"MTF\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 702,

\"trigger_price\": 0,

\"average_price\": 0,

\"filled_quantity\": 0,

\"pending_quantity\": 1,

\"cancelled_quantity\": 1,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": null

}

\]

}

Response attributes¶

attribute

order_id

string

Unique order ID

parent_order_id

string

Order ID of the parent order (only applicable in case of multi-legged
orders like CO)

exchange_order_id

null, string

Exchange generated order ID. Orders that don\'t reach the exchange have
null IDs

modified

bool

Indicate that the order has been modified since placement by the user

placed_by

string

ID of the user that placed the order. This may different from the
user\'s ID for orders placed outside of Kite, for instance, by dealers
at the brokerage using dealer terminals

variety

string

Order variety (regular, amo, co etc.)

status

string

Current status of the order. Most common values or COMPLETE, REJECTED,
CANCELLED, and OPEN. There may be other values as well.

tradingsymbol

string

Exchange tradingsymbol of the instrument

exchange

string

Exchange

instrument_token

string

The numerical identifier issued by the exchange representing the
instrument. Used for subscribing to live market data over WebSocket

transaction_type

string

BUY or SELL

order_type

string

Order type (MARKET, LIMIT etc.)

product

string\>

Margin product to use for the order (margins are blocked based on this)
?

validity

string

Order validity

price

float64

Price at which the order was placed (LIMIT orders)

quantity

int64

Quantity ordered

trigger_price

float64

Trigger price (for SL, SL-M, CO orders)

average_price

float64

Average price at which the order was executed (only for COMPLETE orders)

pending_quantity

int64

Pending quantity to be filled

filled_quantity

int64

Quantity that\'s been filled

disclosed_quantity

int64

Quantity to be disclosed (may be different from actual quantity) to the
public exchange orderbook. Only for equities

order_timestamp

string

Timestamp at which the order was registered by the API

exchange_timestamp

string

Timestamp at which the order was registered by the exchange. Orders that
don\'t reach the exchange have null timestamps

exchange_update_timestamp

string

Timestamp at which an order\'s state changed at the exchange

status_message

null, string

Textual description of the order\'s status. Failed orders come with
human readable explanation

status_message_raw

null, string

Raw textual description of the failed order\'s status, as received from
the OMS

cancelled_quantity

int64

Quantity that\'s cancelled

auction_number

string

A unique identifier for a particular auction

meta

{}, string

Map of arbitrary fields that the system may attach to an order.

tag

null, string

An optional tag to apply to an order to identify it (alphanumeric, max
20 chars)

guid

string

Unusable request id to avoid order duplication

Order statuses¶

The status field in the order response shows the current state of the
order. The status values are largely self explanatory. The most common
statuses are OPEN, COMPLETE, CANCELLED, and REJECTED.

An order can traverse through several interim and temporary statuses
during its lifetime. For example, when an order is first placed or
modified, it instantly passes through several stages before reaching its
end state. Some of these are highlighted below.

status

PUT ORDER REQ RECEIVED Order request has been received by the backend

VALIDATION PENDING Order pending validation by the RMS (Risk Management
System)

OPEN PENDING Order is pending registration at the exchange

MODIFY VALIDATION PENDING Order\'s modification values are pending
validation by the RMS

MODIFY PENDING Order\'s modification values are pending registration at
the exchange

TRIGGER PENDING Order\'s placed but the fill is pending based on a
trigger price.

CANCEL PENDING Order\'s cancellation request is pending registration at
the exchange

AMO REQ RECEIVED Same as PUT ORDER REQ RECEIVED, but for AMOs

Tagging orders¶

Often, it may be necessary to tag and filter orders based on various
criteria, for instance, to filter out all orders that came from a
particular application or an api_key of yours. The tag field comes in
handy here. It let\'s you send an arbitrary string while placing an
order. This can be a unique ID, or something that indicates a particular
type or context, for example. When the orderbook is retrieved, this
value will be present in the tag field in the response.

Market protection¶

Market protection is a feature that helps protect against extreme price
movements when placing MARKET and SL-M (stoploss-market) orders. This
feature allows you to set a percentage threshold to limit how much the
order price can deviate from the current market price.

The market_protection parameter accepts the following values:

0: No market protection (default behavior)

0 to 100: Custom market protection percentage (e.g., 2 means 2%
protection, 10 means 10% protection)

-1: Automatic market protection applied by the system as per market
protection guidelines

The protection percentage should be within the circuit limit\'s.

Note

Market protection is only applicable for MARKET and SL-M order types. It
has no effect on LIMIT and SL orders as they already have built-in price
protection.

Auto slice orders¶

When placing orders with autoslice=true for quantities exceeding freeze
limits, the API response remains the same format (single order object),
but the order gets automatically split into multiple smaller orders
internally. Each slice appears as a separate order in your orderbook
with its own order_id. Auto sliced orders can be identified by the
\"autoslice\" tag in the tags array, and child slices will have an
additional tag like \"autoslice:parent_order_id\" to show the
relationship.

Multi-legged orders (CO)¶

Cover orders are \"multi-legged\" orders, where, a single order you
place (first-leg) may spawn new orders (second-leg) based on the
conditions you set on the first-leg order. These orders have special
properties, where the first-leg order creates a position. The position
is exited when the second-leg order is executed or cancelled.

These second-leg orders will have a parent_order_id field indicating the
order_id of its parent order, that is, the first-leg order. This field
may be required while modifying or cancelling an open second-leg order.

Retrieving an order\'s history¶

curl \"https://api.kite.trade/orders/171229000724687\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": \[

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": null,

\"exchange_timestamp\": null,

\"filled_quantity\": 0,

\"instrument_token\": 1,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:06:52\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"PUT ORDER REQ RECEIVED\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": null,

\"exchange_timestamp\": null,

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:06:52\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"VALIDATION PENDING\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": null,

\"exchange_timestamp\": null,

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:06:52\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"OPEN PENDING\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": \"1300000001887410\",

\"exchange_timestamp\": \"2017-12-29 11:06:52\",

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:06:52\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"OPEN\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": \"1300000001887410\",

\"exchange_timestamp\": \"2017-12-29 11:06:52\",

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:08:16\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"MODIFY VALIDATION PENDING\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": \"1300000001887410\",

\"exchange_timestamp\": \"2017-12-29 11:06:52\",

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:08:16\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"MODIFY PENDING\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": \"1300000001887410\",

\"exchange_timestamp\": \"2017-12-29 11:08:16\",

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:08:16\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"MODIFIED\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

},

{

\"average_price\": 0,

\"cancelled_quantity\": 0,

\"disclosed_quantity\": 0,

\"exchange\": \"NSE\",

\"exchange_order_id\": \"1300000001887410\",

\"exchange_timestamp\": \"2017-12-29 11:08:16\",

\"filled_quantity\": 0,

\"instrument_token\": 779521,

\"order_id\": \"171229000724687\",

\"order_timestamp\": \"2017-12-29 11:08:16\",

\"order_type\": \"LIMIT\",

\"parent_order_id\": null,

\"pending_quantity\": 1,

\"placed_by\": \"DA0017\",

\"price\": 300.1,

\"product\": \"CNC\",

\"quantity\": 1,

\"status\": \"OPEN\",

\"status_message\": null,

\"tag\": null,

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"trigger_price\": 0,

\"validity\": \"DAY\",

\"variety\": \"regular\",

\"modified\": false

}

\]

}

Every order, right after being placed, goes through multiple stages
internally in the OMS. Initial validation, RMS (Risk Management System)
checks and so on before it goes to the exchange. In addition, an open
order, when modified, again goes through these stages.

Retrieving all trades¶

While an orders is sent as a single entity, it may be executed in
arbitrary chunks at the exchange depending on market conditions. For
instance, an order for 10 quantity of an instrument can be executed in
chunks of 5, 1, 1, 3 or any such combination. Each individual execution
that fills an order partially is a trade. An order may have one or more
trades.

This API returns a list of all trades generated by all executed orders
for the day.

curl \"https://api.kite.trade/trades\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": \[

{

\"trade_id\": \"10000000\",

\"order_id\": \"200000000000000\",

\"exchange\": \"NSE\",

\"tradingsymbol\": \"SBIN\",

\"instrument_token\": 779521,

\"product\": \"CNC\",

\"average_price\": 420.65,

\"quantity\": 1,

\"exchange_order_id\": \"300000000000000\",

\"transaction_type\": \"BUY\",

\"fill_timestamp\": \"2021-05-31 09:16:39\",

\"order_timestamp\": \"09:16:39\",

\"exchange_timestamp\": \"2021-05-31 09:16:39\"

},

{

\"trade_id\": \"40000000\",

\"order_id\": \"500000000000000\",

\"exchange\": \"CDS\",

\"tradingsymbol\": \"USDINR21JUNFUT\",

\"instrument_token\": 412675,

\"product\": \"MIS\",

\"average_price\": 72.755,

\"quantity\": 1,

\"exchange_order_id\": \"600000000000000\",

\"transaction_type\": \"BUY\",

\"fill_timestamp\": \"2021-05-31 11:18:27\",

\"order_timestamp\": \"11:18:27\",

\"exchange_timestamp\": \"2021-05-31 11:18:27\"

},

{

\"trade_id\": \"70000000\",

\"order_id\": \"800000000000000\",

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL21JUNFUT\",

\"instrument_token\": 58424839,

\"product\": \"NRML\",

\"average_price\": 4852,

\"quantity\": 1,

\"exchange_order_id\": \"312115100078593\",

\"transaction_type\": \"BUY\",

\"fill_timestamp\": \"2021-05-31 16:00:36\",

\"order_timestamp\": \"16:00:36\",

\"exchange_timestamp\": \"2021-05-31 16:00:36\"

},

{

\"trade_id\": \"90000000\",

\"order_id\": \"1100000000000000\",

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL21JUNFUT\",

\"instrument_token\": 58424839,

\"product\": \"NRML\",

\"average_price\": 4852,

\"quantity\": 1,

\"exchange_order_id\": \"1200000000000000\",

\"transaction_type\": \"BUY\",

\"fill_timestamp\": \"2021-05-31 16:08:41\",

\"order_timestamp\": \"16:08:41\",

\"exchange_timestamp\": \"2021-05-31 16:08:41\"

}

\]

}

Response attributes¶

attribute

trade_id

string

Exchange generated trade ID

order_id

string

Unique order ID

exchange_order_id

null, string

Exchange generated order ID

tradingsymbol

string

Exchange tradingsymbol of the instrument

exchange

string

Exchange

instrument_token

string

The numerical identifier issued by the exchange representing the
instrument. Used for subscribing to live market data over WebSocket

transaction_type

string

BUY or SELL

product

string

Margin product to use for the order (margins are blocked based on this)
?

average_price

float64

Price at which the quantity was filled

filled

int64

Filled quantity

fill_timestamp

string

Timestamp at which the trade was filled at the exchange

order_timestamp

string

Timestamp at which the order was registered by the API

exchange_timestamp

string

Timestamp at which the order was registered by the exchange

Retrieving an order\'s trades¶

This API returns the trades spawned and executed by a particular order.

curl \"https://api.kite.trade/orders/200000000000000/trades\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": \[

{

\"trade_id\": \"10000000\",

\"order_id\": \"200000000000000\",

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL21JUNFUT\",

\"instrument_token\": 58424839,

\"product\": \"NRML\",

\"average_price\": 4852,

\"quantity\": 1,

\"exchange_order_id\": \"300000000000000\",

\"transaction_type\": \"BUY\",

\"fill_timestamp\": \"2021-05-31 16:00:36\",

\"order_timestamp\": \"16:00:36\",

\"exchange_timestamp\": \"2021-05-31 16:00:36\"

}

\]

}\
Market quotes and instruments¶

type endpoint

GET /instruments Retrieve the CSV dump of all tradable instruments

GET /instruments/:exchange Retrieve the CSV dump of instruments in the
particular exchange

GET /quote Retrieve full market quotes for one or more instruments

GET /quote/ohlc Retrieve OHLC quotes for one or more instruments

GET /quote/ltp Retrieve LTP quotes for one or more instruments

Instruments¶

Between multiple exchanges and segments, there are tens of thousands of
different kinds of instruments that trade. Any application that
facilitates trading needs to have a master list of these instruments.
The instruments API provides a consolidated, import-ready CSV list of
instruments available for trading.

Retrieving the full instrument list¶

Unlike the rest of the calls that return JSON, the instrument list API
returns a gzipped CSV dump of instruments across all exchanges that can
be imported into a database. The dump is generated once everyday and
hence last_price is not real time.

curl \"https://api.kite.trade/instruments\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

instrument_token, exchange_token, tradingsymbol, name, last_price,
expiry, strike, tick_size, lot_size, instrument_type, segment, exchange

408065,1594,INFY,INFOSYS,0,,,0.05,1,EQ,NSE,NSE

5720322,22345,NIFTY15DECFUT,,78.0,2015-12-31,,0.05,75,FUT,NFO-FUT,NFO

5720578,22346,NIFTY159500CE,,23.0,2015-12-31,9500,0.05,75,CE,NFO-OPT,NFO

645639,SILVER15DECFUT,,7800.0,2015-12-31,,1,1,FUT,MCX,MCX

CSV response columns¶

column

instrument_token

string

Numerical identifier used for subscribing to live market quotes with the
WebSocket API.

exchange_token

string

The numerical identifier issued by the exchange representing the
instrument.

tradingsymbol

string

Exchange tradingsymbol of the instrument

name

string

Name of the company (for equity instruments)

last_price

float64

Last traded market price

expiry

string

Expiry date (for derivatives)

strike

float64

Strike (for options)

tick_size

float64

Value of a single price tick

lot_size

int64

Quantity of a single lot

instrument_type

string

EQ, FUT, CE, PE

segment

string

Segment the instrument belongs to

exchange

string

Exchange

Warning

The instrument list API returns large amounts of data. It\'s best to
request it once a day (ideally at around 08:30 AM) and store in a
database at your end.

Note

For storage, it is recommended to use a combination of exchange and
tradingsymbol as the unique key, not the numeric instrument token.
Exchanges may reuse instrument tokens for different derivative
instruments after each expiry.

Market quotes¶

The market quotes APIs enable you to retrieve market data snapshots of
various instruments. These are snapshots gathered from the exchanges at
the time of the request. For realtime streaming market quotes, use the
WebSocket API.

Retrieving full market quotes¶

This API returns the complete market data snapshot of up to 500
instruments in one go. It includes the quantity, OHLC, and Open Interest
fields, and the complete bid/ask market depth amongst others.

Instruments are identified by the exchange:tradingsymbol combination and
are passed as values to the query parameter i which is repeated for
every instrument. If there is no data available for a given key, the key
will be absent from the response. The existence of all the instrument
keys in the response map should be checked before to accessing them.

curl \"https://api.kite.trade/quote?i=NSE:INFY\" \\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": {

\"NSE:INFY\": {

\"instrument_token\": 408065,

\"timestamp\": \"2021-06-08 15:45:56\",

\"last_trade_time\": \"2021-06-08 15:45:52\",

\"last_price\": 1412.95,

\"last_quantity\": 5,

\"buy_quantity\": 0,

\"sell_quantity\": 5191,

\"volume\": 7360198,

\"average_price\": 1412.47,

\"oi\": 0,

\"oi_day_high\": 0,

\"oi_day_low\": 0,

\"net_change\": 0,

\"lower_circuit_limit\": 1250.7,

\"upper_circuit_limit\": 1528.6,

\"ohlc\": {

\"open\": 1396,

\"high\": 1421.75,

\"low\": 1395.55,

\"close\": 1389.65

},

\"depth\": {

\"buy\": \[

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

}

\],

\"sell\": \[

{

\"price\": 1412.95,

\"quantity\": 5191,

\"orders\": 13

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

},

{

\"price\": 0,

\"quantity\": 0,

\"orders\": 0

}

\]

}

}

}

}

Response attributes¶

attribute

instrument_token

uint32

The numerical identifier issued by the exchange representing the
instrument.

timestamp

string

The exchange timestamp of the quote packet

last_trade_time

null, string

Last trade timestamp

last_price

float64

Last traded market price

volume

int64

Volume traded today

average_price

float64

The volume weighted average price of a stock at a given time during the
day?

buy_quantity

int64

Total quantity of buy orders pending at the exchange

sell_quantity

int64

Total quantity of sell orders pending at the exchange

open_interest

float64

Total number of outstanding contracts held by market participants
exchange-wide (only F&O)

last_quantity

int64

Last traded quantity

ohlc.open

float64

Price at market opening

ohlc.high

float64

Highest price today

ohlc.low

float64

Lowest price today

ohlc.close

float64

Closing price of the instrument from the last trading day

net_change

float64

The absolute change from yesterday\'s close to last traded price

lower_circuit_limit

float64

The current lower circuit limit

upper_circuit_limit

float64

The current upper circuit limit

oi

float64

The Open Interest for a futures or options contract ?

oi_day_high

float64

The highest Open Interest recorded during the day

oi_day_low

float64

The lowest Open Interest recorded during the day

depth.buy\[\].price

float64

Price at which the depth stands

depth.buy\[\].orders

int64

Number of open BUY (bid) orders at the price

depth.buy\[\].quantity

int64

Net quantity from the pending orders

depth.sell\[\].price

float64

Price at which the depth stands

depth.sell\[\].orders

int64

Number of open SELL (ask) orders at the price

depth.sell\[\].quantity

int64

Net quantity from the pending orders

Retrieving OHLC quotes¶

This API returns the OHLC + LTP snapshots of up to 1000 instruments in
one go.

Instruments are identified by the exchange:tradingsymbol combination and
are passed as values to the query parameter i which is repeated for
every instrument. If there is no data available for a given key, the key
will be absent from the response. The existence of all the instrument
keys in the response map should be checked before to accessing them.

curl
\"https://api.kite.trade/quote/ohlc?i=NSE:INFY&i=BSE:SENSEX&i=NSE:NIFTY+50\"
\\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": {

\"NSE:INFY\": {

\"instrument_token\": 408065,

\"last_price\": 1075,

\"ohlc\": {

\"open\": 1085.8,

\"high\": 1085.9,

\"low\": 1070.9,

\"close\": 1075.8

}

}

}

}

Response attributes¶

attribute

instrument_token

uint32

The numerical identifier issued by the exchange representing the
instrument.

last_price

float64

Last traded market price

ohlc.open

float64

Price at market opening

ohlc.high

float64

Highest price today

ohlc.low

float64

Lowest price today

ohlc.close

float64

Closing price of the instrument from the last trading day

Note

Always check for the existence of a particular key you\'ve requested
(eg: NSE:INFY) in the response. If there\'s no data for the particular
instrument or if it has expired, the key will be missing from the
response.

Retrieving LTP quotes¶

This API returns the LTPs of up to 1000 instruments in one go.

Instruments are identified by the exchange:tradingsymbol combination and
are passed as values to the query parameter i which is repeated for
every instrument. If there is no data available for a given key, the key
will be absent from the response. The existence of all the instrument
keys in the response map should be checked before to accessing them.

curl
\"https://api.kite.trade/quote/ltp?i=NSE:INFY&i=BSE:SENSEX&i=NSE:NIFTY+50\"
\\

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\"

{

\"status\": \"success\",

\"data\": {

\"NSE:INFY\": {

\"instrument_token\": 408065,

\"last_price\": 1074.35

}

}

}

Response attributes¶

attribute

instrument_token

uint32

The numerical identifier issued by the exchange representing the
instrument.

last_price

float64

Last traded market price

Note

Always check for the existence of a particular key you\'ve requested
(eg: NSE:INFY) in the response. If there\'s no data for the particular
instrument or if it has expired, the key will be absent from the
response.

Limits¶

attribute number of instruments

/quote 500

/quote/ohlc 1000

/quote/ltp 1000\
\
\
\
WebSocket streaming¶

The WebSocket API is the most efficient (speed, latency, resource
consumption, and bandwidth) way to receive quotes for instruments across
all exchanges during live market hours. A quote consists of fields such
as open, high, low, close, last traded price, 5 levels of bid/offer
market depth data etc.

In addition, the text messages, alerts, and order updates (the same as
the ones available as Postbacks) are also streamed. As the name
suggests, the API uses WebSocket protocol to establish a single long
standing TCP connection after an HTTP handshake to receive streaming
quotes. To connect to the Kite WebSocket API, you will need a WebSocket
client library in your choice of programming language.

You can subscribe for up to 3000 instruments on a single WebSocket
connection and receive live quotes for them. Single API key can have
upto 3 websocket connections.

Note

Implementing an asynchronous WebSocket client with a binary parser for
the market data structure may be a complex task. We recommend using one
of our pre-built client libraries.

Connecting to the WebSocket endpoint¶

// Javascript example.

var ws = new
WebSocket(\"wss://ws.kite.trade?api_key=xxx&access_token=xxxx\");

The WebSocket endpoint is wss://ws.kite.trade. To establish a
connection, you have to pass two query parameters, api_key and
access_token.

Request structure¶

// Subscribe to quotes for INFY (408065) and TATAMOTORS (884737)

var message = { a: \"subscribe\", v: \[408065, 884737\] };

ws.send(JSON.stringify(message));

Requests are simple JSON messages with two parameters, a (action) and v
(value). Following are the available actions and possible values. Many
values are arrays, for instance, array of instrument_token that can be
passed to subscribe to multiple instruments at once.

a v

subscribe \[instrument_token \... \]

unsubscribe \[instrument_token \... \]

mode \[mode, \[instrument_token \... \]\]

// Set INFY (408065) to \'full\' mode to

// receive market depth as well.

message = { a: \"mode\", v: \[\"full\", \[408065\]\] };

ws.send(JSON.stringify(message));

// Set TATAMOTORS (884737) to \'ltp\' to only receive the LTP.

message = { a: \"mode\", v: \[\"ltp\", \[884737\]\] };

ws.send(JSON.stringify(message));

Modes¶

There are three different modes in which quote packets are streamed.

mode

ltp LTP. Packet contains only the last traded price (8 bytes).

quote Quote. Packet contains several fields excluding market depth (44
bytes).

full Full. Packet contains several fields including market depth (184
bytes).

Note

Always check the type of an incoming WebSocket messages. Market data is
always binary and Postbacks and other updates are always text.

If there is no data to be streamed over an open WebSocket connection,
the API will send a 1 byte \"heartbeat\" every couple seconds to keep
the connection alive. This can be safely ignored.

Binary market data¶

WebSocket supports two types of messages, binary and text.

Quotes delivered via the API are always binary messages. These have to
be read as bytes and then type-casted into appropriate quote data
structures. On the other hand, all requests you send to the API are JSON
messages, and the API may also respond with non-quote, non-binary JSON
messages, which are described in the next section.

For quote subscriptions, instruments are identified with their
corresponding numerical instrument_token obtained from the instrument
list API.

Message structure¶

Each binary message (array of 0 to n individual bytes)\--or frame in
WebSocket terminology\--received via the WebSocket is a combination of
one or more quote packets for one or more instruments. The message
structure is as follows.

WebSocket API message structure

A The first two bytes (\[0 - 2\] \-- SHORT or int16) represent the
number of packets in the message.

B The next two bytes (\[2 - 4\] \-- SHORT or int16) represent the length
(number of bytes) of the first packet.

C The next series of bytes (\[4 - 4+B\]) is the quote packet.

D The next two bytes (\[4+B - 4+B+2\] \-- SHORT or int16) represent the
length (number of bytes) of the second packet.

C The next series of bytes (\[4+B+2 - 4+B+2+D\]) is the next quote
packet.

Quote packet structure¶

Each individual packet extracted from the message, based on the
structure shown in the previous section, can be cast into a data
structure as follows. All prices are in paise. For currencies, the int32
price values should be divided by 10000000 to obtain four decimal plaes.
For everything else, the price values should be divided by 100.

Bytes Type

0 - 4 int32 instrument_token

4 - 8 int32 Last traded price (If mode is ltp, the packet ends here)

8 - 12 int32 Last traded quantity

12 - 16 int32 Average traded price

16 - 20 int32 Volume traded for the day

20 - 24 int32 Total buy quantity

24 - 28 int32 Total sell quantity

28 - 32 int32 Open price of the day

32 - 36 int32 High price of the day

36 - 40 int32 Low price of the day

40 - 44 int32 Close price (If mode is quote, the packet ends here)

44 - 48 int32 Last traded timestamp

48 - 52 int32 Open Interest

52 - 56 int32 Open Interest Day High

56 - 60 int32 Open Interest Day Low

60 - 64 int32 Exchange timestamp

64 - 184 \[\]byte Market depth entries

Index packet structure¶

The packet structure for indices such as NIFTY 50 and SENSEX differ from
that of tradeable instruments. They have fewer fields.

Bytes Type

0 - 4 int32 Token

4 - 8 int32 Last traded price

8 - 12 int32 High of the day

12 - 16 int32 Low of the day

16 - 20 int32 Open of the day

20 - 24 int32 Close of the day

24 - 28 int32 Price change (If mode is quote, the packet ends here)

28 - 32 int32 Exchange timestamp

Market depth structure¶

Each market depth entry is a combination of 3 fields, quantity (int32),
price (int32), orders (int16) and there is a 2 byte padding at the end
(which should be skipped) totalling to 12 bytes. There are ten entries
in succession---five \[64 - 124\] bid entries and five \[124 - 184\]
offer entries.

Postbacks and non-binary updates¶

Apart from binary market data, the WebSocket stream delivers postbacks
and other updates in the text mode. These messages are JSON encoded and
should be parsed on receipt. For order Postbacks, the payload is
contained in the data key and has the same structure described in the
Postbacks section.

Message structure

{

\"type\": \"order\",

\"data\": {}

}

Message types¶

type

order Order Postback. The data field will contain the full order
Postback payload

error Error responses. The data field contain the error string

message Messages and alerts from the broker. The data field will contain
the message string\
\
\
\
\
\
\
Historical candle data¶

The historical data API provides archived data (up to date as of the
time of access) for instruments across various exchanges spanning back
several years. A historical record is presented in the form of a candle
(Timestamp, Open, High, Low, Close, Volume, OI), and the data is
available in several intervals---minute, 3 minutes, 5 minutes, hourly
\... daily.

type endpoint

GET /instruments/historical/:instrument_token/:interval Retrieve
historical candle records for a given instrument.

URI parameters¶

parameter

:instrument_token Identifier for the instrument whose historical records
you want to fetch. This is obtained with the instrument list API.

:interval The candle record interval. Possible values are:

· minute

· day

· 3minute

· 5minute

· 10minute

· 15minute

· 30minute

· 60minute

Request parameters¶

parameter

from yyyy-mm-dd hh:mm:ss formatted date indicating the start date of
records

to yyyy-mm-dd hh:mm:ss formatted date indicating the end date of records

continuous Accepts 0 or 1. Pass 1 to get continuous data

oi Accepts 0 or 1. Pass 1 to get OI data

Response structure¶

The response is an array of records, where each record in turn is an
array of the following values --- \[timestamp, open, high, low, close,
volume\].

Note

It is possible to retrieve candles for small time intervals by making
the from and to calls granular. For instance from = 2017-01-01 09:15:00
and to = 2017-01-01 09:30:00 to fetch candles for just 15 minutes
between those timestamps.

Continuous data¶

It\'s important to note that the exchanges flush the instrument_token
for futures and options contracts for every expiry. For instance,
NIFTYJAN18FUT and NIFTYFEB18FUT will have different instrument tokens
although their underlying contract is the same. The instrument master
API only returns instrument_tokens for contracts that are live. It is
not possible to retrieve instrument_tokens for expired contracts from
the API, unless you regularly download and cache them.

This is where continuous API comes in which works for NFO and MCX
futures contracts. Given a live contract\'s instrument_token, the API
will return day candle records for the same instrument\'s expired
contracts. For instance, assuming the current month is January and you
pass NIFTYJAN18FUT\'s instrument_token along with continuous=1, you can
fetch day candles for December, November \... contracts by simply
changing the from and to dates.

Examples¶

\# Fetch minute candles for NSE-ACC.

\# This will return several days of minute data ending today.

\# The time of request is assumed to be to be 01:30 PM, 1 Jan 2016,

\# which is reflected in the latest (last) record.

\# The data has been truncated with \... in the example responses.

curl
\"https://api.kite.trade/instruments/historical/5633/minute?from=2017-12-15+09:15:00&to=2017-12-15+09:20:00\"

-H \"X-Kite-Version: 3\" \\

-H \"Authorization: token api_key:access_token\" \\

{

\"status\": \"success\",

\"data\": {

\"candles\": \[

\[

\"2017-12-15T09:15:00+0530\",

1704.5,

1705,

1699.25,

1702.8,

2499

\],

\[

\"2017-12-15T09:16:00+0530\",

1702,

1702,

1698.15,

1698.15,

1271

\],

\[

\"2017-12-15T09:17:00+0530\",

1698.15,

1700.25,

1698,

1699.25,

831

\],

\[

\"2017-12-15T09:18:00+0530\",

1700,

1700,

1698.3,

1699,

771

\],

\[

\"2017-12-15T09:19:00+0530\",

1699,

1700,

1698.1,

1699.8,

543

\],

\[

\"2017-12-15T09:20:00+0530\",

1699.8,

1700,

1696.55,

1696.9,

802

\]

\]

}

}

OI Data¶

\# Fetch minute candles for NIFTY19DECFUT for five minutes with OI data

curl
\"https://api.kite.trade/instruments/historical/12517890/minute?from=2019-12-04%2009:15:00&to=2019-12-04%2009:20:00&oi=1\"
\\

-H \'X-Kite-Version: 3\' \\

-H \'Authorization: token api_key:access_token\'

{

\"status\": \"success\",

\"data\": {

\"candles\": \[

\[

\"2019-12-04T09:15:00+0530\",

12009.9,

12019.35,

12001.25,

12001.5,

163275,

13667775

\],

\[

\"2019-12-04T09:16:00+0530\",

12001,

12003,

11998.25,

12001,

105750,

13667775

\],

\[

\"2019-12-04T09:17:00+0530\",

12001,

12001,

11995.1,

11998.55,

48450,

13758000

\],

\[

\"2019-12-04T09:18:00+0530\",

11997.8,

12002,

11996.25,

12001.55,

52875,

13758000

\],

\[

\"2019-12-04T09:19:00+0530\",

12002.35,

12007,

12001.45,

12007,

52200,

13758000

\],

\[

\"2019-12-04T09:20:00+0530\",

12006.95,

12009.25,

11999.6,

11999.6,

65325,

13777050

\]

\]

}

}\
Postback (WebHooks)¶

The Postback API sends a POST request with a JSON payload to the
registered postback_url of your app when an order\'s status changes.
This enables you to get arbitrary updates to your orders reliably,
irrespective of when they happen (COMPLETE, CANCEL, REJECTED, UPDATE).
An UPDATE postback is triggered when an open order is modified or when
there\'s a partial fill. This can be used to track trades.

Note

This Postback API is meant for platforms and public apps where a single
api_key will place orders for multiple users. Only orders placed using
the app\'s api_key are notified.

For individual developers, Postbacks over WebSocket is recommended,
where, orders placed for a particular user anywhere, for instance, web,
mobile, or desktop platforms, are sent.

The JSON payload is posted as a raw HTTP POST body. You will have to
read the raw body and then decode it.

Sample payload

{

\"user_id\": \"AB1234\",

\"unfilled_quantity\": 0,

\"app_id\": 1234,

\"checksum\":
\"2011845d9348bd6795151bf4258102a03431e3bb12a79c0df73fcb4b7fde4b5d\",

\"placed_by\": \"AB1234\",

\"order_id\": \"220303000308932\",

\"exchange_order_id\": \"1000000001482421\",

\"parent_order_id\": null,

\"status\": \"COMPLETE\",

\"status_message\": null,

\"status_message_raw\": null,

\"order_timestamp\": \"2022-03-03 09:24:25\",

\"exchange_update_timestamp\": \"2022-03-03 09:24:25\",

\"exchange_timestamp\": \"2022-03-03 09:24:25\",

\"variety\": \"regular\",

\"exchange\": \"NSE\",

\"tradingsymbol\": \"SBIN\",

\"instrument_token\": 779521,

\"order_type\": \"MARKET\",

\"transaction_type\": \"BUY\",

\"validity\": \"DAY\",

\"product\": \"CNC\",

\"quantity\": 1,

\"disclosed_quantity\": 0,

\"price\": 0,

\"trigger_price\": 0,

\"average_price\": 470,

\"filled_quantity\": 1,

\"pending_quantity\": 0,

\"cancelled_quantity\": 0,

\"market_protection\": 0,

\"meta\": {},

\"tag\": null,

\"guid\": \"XXXXXX\"

}

Checksum¶

The JSON payload comes with a checksum, which is the SHA-256 hash of
(order_id + order_timestamp + api_secret). For every Postback you
receive, you should compute this checksum at your end and match it with
the checksum in the payload. This is to ensure that the update is being
POSTed by Kite Connect and not by an unauthorised entity, as only Kite
Connect can generate a checksum that contains your api_secret.

Payload attributes¶

attribute

order_id

string

Unique order ID

exchange_order_id

null, string

Exchange generated order id. Orders that don\'t reach the exchange have
null ids

parent_order_id

null, string

Order ID of the parent order (only applicable in case of multi-legged
orders like CO)

placed_by

string

ID of the user that placed the order. This may different from the
user\'s id for orders placed outside of Kite, for instance, by dealers
at the brokerage using dealer terminals.

app_id

int64

Your kiteconnect app ID

status

null, string

Current status of the order. The possible values are COMPLETE, REJECTED,
CANCELLED, and UPDATE.

status_message

null, string

Textual description of the order\'s status. Failed orders come with
human readable explanation

status_message_raw

null, string

Raw textual description of the failed order\'s status, as received from
the OMS

tradingsymbol

string

Exchange tradingsymbol of the of the instrument

instrument_token

uint32

The numerical identifier issued by the exchange representing the
instrument

exchange

string

Exchange

order_type

string

Order type (MARKET, LIMIT etc.)

transaction_type

string

BUY or SELL

validity

string

Order validity

variety

string

Order variety (regular, amo, co etc.)

product

string

Margin product to use for the order

average_price

float64

Average price at which the order was executed (only for COMPLETE orders)

disclosed_quantity

int64

Quantity to be disclosed (may be different from actual quantity) to the
public exchange orderbook. Only for equities

price

float64

Price at which the order was placed (LIMIT orders)

quantity

int64

Quantity ordered

filled_quantity

int64

Quantity that has been filled

unfilled_quantity

int64

Quantity that has not filled

pending_quantity

int64

Pending quantity for open order

cancelled_quantity

int64

Quantity that had been cancelled

trigger_price

float64

Trigger price (for SL, SL-M, CO orders)

user_id

string

ID of the user for whom the order was placed.

order_timestamp

string

Timestamp at which the order was registered by the API

exchange_update_timestamp

string

Timestamp at which an order\'s state changed at the exchange

exchange_timestamp

string

Timestamp at which the order was registered by the exchange. Orders that
don\'t reach the exchange have null timestamps

checksum

string

SHA-256 hash of (order_id + timestamp + api_secret)

meta

{}, string

Map of arbitrary fields that the system may attach to an order

tag

null, string

An optional tag to apply to an order to identify it (alphanumeric, max
20 chars)

Note

Postback API works even when the user is not logged in. Just make sure
you validate the checksum value to ensure that the update is indeed
coming from Kite Connect.\
\
Margin calculation¶

Margin calculation APIs lets you calculate span, exposure, option
premium, additional, bo, cash, var, pnl values for a list of orders.

type endpoint

POST /margins/orders Calculates margins for each order considering the
existing positions and open orders

POST /margins/basket Calculates margins for spread orders

POST /charges/orders Calculates order-wise charges for orderbook

Note

Requests to the above endpoints are JSON POST and it needs
application/json header.

Order margins¶

Request order structure

Response margin structure

curl https://api.kite.trade/margins/orders \\

-H \'X-Kite-Version: 3\' \\

-H \'Authorization: token api_key:access_token\' \\

-H \'Content-Type: application/json\' \\

-d \'\[

{

\"exchange\": \"NSE\",

\"tradingsymbol\": \"INFY\",

\"transaction_type\": \"BUY\",

\"variety\": \"regular\",

\"product\": \"CNC\",

\"order_type\": \"MARKET\",

\"quantity\": 1,

\"price\": 0,

\"trigger_price\": 0

}

\]\'

Query parameters are as follows.

parameter

mode compact - Compact mode will only give the total margins

{

\"status\": \"success\",

\"data\": \[

{

\"type\": \"equity\",

\"tradingsymbol\": \"INFY\",

\"exchange\": \"NSE\",

\"span\": 0,

\"exposure\": 0,

\"option_premium\": 0,

\"additional\": 0,

\"bo\": 0,

\"cash\": 0,

\"var\": 1498,

\"pnl\": {

\"realised\": 0,

\"unrealised\": 0

},

\"leverage\": 1,

\"charges\": {

\"transaction_tax\": 1.498,

\"transaction_tax_type\": \"stt\",

\"exchange_turnover_charge\": 0.051681,

\"sebi_turnover_charge\": 0.001498,

\"brokerage\": 0.01,

\"stamp_duty\": 0.22,

\"gst\": {

\"igst\": 0.011372219999999999,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0.011372219999999999

},

\"total\": 1.79255122

},

\"total\": 1498

}

\]

}

Order structure¶

parameter

exchange Name of the exchange

transaction_type BUY/SELL

variety Order variety (regular, amo, co etc.)

product Margin product to use for the order (margins are blocked based
on this) ?

order_type Order type (MARKET, LIMIT etc.)

quantity Quantity of the order

price Price at which the order is going to be placed (LIMIT orders)

trigger_price Trigger price (for SL, SL-M, CO orders)

Margin structure¶

parameter

type equity/commodity

tradingsymbol Trading symbol of the instrument

exchange Name of the exchange

span SPAN margins

exposure Exposure margins

option_premium Option premium

additional Additional margins

bo BO margins

cash Cash credit

var VAR

pnl Realised and unrealised profit and loss

leverage Margin leverage allowed for the trade

charges The breakdown of the various charges that will be applied to an
order

total Total margin block

Charges structure¶

Field Definition

total Total charges

transaction_tax Tax levied for each transaction on the exchanges

transaction_tax_type Type of transaction tax

exchange_turnover_charge Charge levied by the exchange on the total
turnover of the day

sebi_turnover_charge Charge levied by SEBI on the total turnover of the
day

brokerage The brokerage charge for a particular trade

stamp_duty Duty levied on the transaction value by Government of India

gst.igst Integrated Goods and Services Tax levied by the government

gst.cgst Central Goods and Services Tax levied by the government

gst.sgst State Goods and Services Tax levied by the government

gst.total Total GST

Basket margins¶

curl https://api.kite.trade/margins/basket?consider_positions=true \\

-H \'X-Kite-Version: 3\' \\

-H \'Authorization: token api_key:access_token\' \\

-H \'Content-Type: application/json\' \\

-d \'\[

{

\"exchange\": \"NFO\",

\"tradingsymbol\": \"NIFTY23JUL20600CE\",

\"transaction_type\": \"SELL\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"MARKET\",

\"quantity\": 75,

\"price\": 0,

\"trigger_price\": 0

},

{

\"exchange\": \"NFO\",

\"tradingsymbol\": \"NIFTY23JUL20700CE\",

\"transaction_type\": \"BUY\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"MARKET\",

\"quantity\": 75,

\"price\": 0,

\"trigger_price\": 0

}

\]\'

Query parameters are as follows.

parameter

consider_positions Boolean to consider users positions

mode compact - Compact mode will only give the total margins

{

\"status\": \"success\",

\"data\": {

\"initial\": {

\"type\": \"\",

\"tradingsymbol\": \"\",

\"exchange\": \"\",

\"span\": 66832.5,

\"exposure\": 29151.225000000002,

\"option_premium\": 521.25,

\"additional\": 0,

\"bo\": 0,

\"cash\": 0,

\"var\": 0,

\"pnl\": {

\"realised\": 0,

\"unrealised\": 0

},

\"leverage\": 0,

\"charges\": {

\"transaction_tax\": 0,

\"transaction_tax_type\": \"\",

\"exchange_turnover_charge\": 0,

\"sebi_turnover_charge\": 0,

\"brokerage\": 0,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 0,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0

},

\"total\": 0

},

\"total\": 96504.975

},

\"final\": {

\"type\": \"\",

\"tradingsymbol\": \"\",

\"exchange\": \"\",

\"span\": 7788.000000000007,

\"exposure\": 29151.225000000002,

\"option_premium\": -2152.5,

\"additional\": 0,

\"bo\": 0,

\"cash\": 0,

\"var\": 0,

\"pnl\": {

\"realised\": 0,

\"unrealised\": 0

},

\"leverage\": 0,

\"charges\": {

\"transaction_tax\": 0,

\"transaction_tax_type\": \"\",

\"exchange_turnover_charge\": 0,

\"sebi_turnover_charge\": 0,

\"brokerage\": 0,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 0,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0

},

\"total\": 0

},

\"total\": 34786.725000000006

},

\"orders\": \[

{

\"type\": \"equity\",

\"tradingsymbol\": \"NIFTY23JUL20600CE\",

\"exchange\": \"NFO\",

\"span\": 66832.5,

\"exposure\": 29151.225000000002,

\"option_premium\": 0,

\"additional\": 0,

\"bo\": 0,

\"cash\": 0,

\"var\": 0,

\"pnl\": {

\"realised\": 0,

\"unrealised\": 0

},

\"leverage\": 1,

\"charges\": {

\"transaction_tax\": 1.67109375,

\"transaction_tax_type\": \"stt\",

\"exchange_turnover_charge\": 1.336875,

\"sebi_turnover_charge\": 0.00267375,

\"brokerage\": 20,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 3.8411187749999995,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 3.8411187749999995

},

\"total\": 26.851761274999998

},

\"total\": 95983.725

},

{

\"type\": \"equity\",

\"tradingsymbol\": \"NIFTY23JUL20700CE\",

\"exchange\": \"NFO\",

\"span\": 0,

\"exposure\": 0,

\"option_premium\": 521.25,

\"additional\": 0,

\"bo\": 0,

\"cash\": 0,

\"var\": 0,

\"pnl\": {

\"realised\": 0,

\"unrealised\": 0

},

\"leverage\": 1,

\"charges\": {

\"transaction_tax\": 0,

\"transaction_tax_type\": \"stt\",

\"exchange_turnover_charge\": 0.260625,

\"sebi_turnover_charge\": 0.00052125,

\"brokerage\": 20,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 3.6470063249999995,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 3.6470063249999995

},

\"total\": 23.908152575

},

\"total\": 521.25

}

\],

\"charges\": {

\"transaction_tax\": 0,

\"transaction_tax_type\": \"\",

\"exchange_turnover_charge\": 0,

\"sebi_turnover_charge\": 0.003195,

\"brokerage\": 40,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 0,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0

},

\"total\": 0

}

}

}

Response structure is as follows.

parameter

initial Total margins required to execute the orders

final Total margins with the spread benefit

orders Individual margins per order

charges Final charges block

Note

The final charges block can be ignored as it may not include
transaction_tax charges because baskets can contain both mcx and equity
instruments, with different tax types (STT or CTT). Users can refer to
the individual order charges response in the orders block.

Virtual contract note¶

A virtual contract provides detailed charges order-wise for brokerage,
STT, stamp duty, exchange transaction charges, SEBI turnover charge, and
GST.

curl https://api.kite.trade/charges/orders \\

-H \'X-Kite-Version: 3\' \\

-H \'Authorization: token api_key:access_token\' \\

-H \'Content-Type: application/json\' \\

-d \'\[

{

\"order_id\": \"111111111\",

\"exchange\": \"NSE\",

\"tradingsymbol\": \"SBIN\",

\"transaction_type\": \"BUY\",

\"variety\": \"regular\",

\"product\": \"CNC\",

\"order_type\": \"MARKET\",

\"quantity\": 1,

\"average_price\": 560

},

{

\"order_id\": \"2222222222\",

\"exchange\": \"MCX\",

\"tradingsymbol\": \"GOLDPETAL23JULFUT\",

\"transaction_type\": \"SELL\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"LIMIT\",

\"quantity\": 1,

\"average_price\": 5862

},

{

\"order_id\": \"3333333333\",

\"exchange\": \"NFO\",

\"tradingsymbol\": \"NIFTY2371317900PE\",

\"transaction_type\": \"BUY\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"LIMIT\",

\"quantity\": 100,

\"average_price\": 1.5

}

\]\'

Order structure¶

parameter

order_id

string

Unique order ID (It can be any random string to calculate charges for an
imaginary order)

exchange

string

Name of the exchange

tradingsymbol

string

Exchange tradingsymbol of the instrument

transaction_type

string

BUY/SELL

variety

string

Order variety (regular, amo, co etc.)

product

string

Margin product to use for the order (margins are blocked based on this)
?

order_type

string

Order type (MARKET, LIMIT etc.)

quantity

int64

Quantity of the order

average_price

float64

Average price at which the order was executed (Note: Should be
non-zero).

{

\"status\": \"success\",

\"data\": \[

{

\"transaction_type\": \"BUY\",

\"tradingsymbol\": \"SBIN\",

\"exchange\": \"NSE\",

\"variety\": \"regular\",

\"product\": \"CNC\",

\"order_type\": \"MARKET\",

\"quantity\": 1,

\"price\": 560,

\"charges\": {

\"transaction_tax\": 0.56,

\"transaction_tax_type\": \"stt\",

\"exchange_turnover_charge\": 0.01876,

\"sebi_turnover_charge\": 0.00056,

\"brokerage\": 0,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 0.0033767999999999997,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0.0033767999999999997

},

\"total\": 0.5826968

}

},

{

\"transaction_type\": \"SELL\",

\"tradingsymbol\": \"GOLDPETAL23JULFUT\",

\"exchange\": \"MCX\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"LIMIT\",

\"quantity\": 1,

\"price\": 5862,

\"charges\": {

\"transaction_tax\": 0.5862,

\"transaction_tax_type\": \"ctt\",

\"exchange_turnover_charge\": 0.152412,

\"sebi_turnover_charge\": 0.005862,

\"brokerage\": 1.7586,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 0.34503732,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 0.34503732

},

\"total\": 2.84811132

}

},

{

\"transaction_type\": \"BUY\",

\"tradingsymbol\": \"NIFTY2371317900PE\",

\"exchange\": \"NFO\",

\"variety\": \"regular\",

\"product\": \"NRML\",

\"order_type\": \"LIMIT\",

\"quantity\": 100,

\"price\": 1.5,

\"charges\": {

\"transaction_tax\": 0,

\"transaction_tax_type\": \"stt\",

\"exchange_turnover_charge\": 0.07575,

\"sebi_turnover_charge\": 0.00015,

\"brokerage\": 20,

\"stamp_duty\": 0,

\"gst\": {

\"igst\": 3.613527,

\"cgst\": 0,

\"sgst\": 0,

\"total\": 3.613527

},

\"total\": 23.689427000000002

}

}

\]

}

Response attributes¶

attribute

transaction_type

string

Type of transaction being processed(BUY/SELL).

tradingsymbol

string

Exchange tradingsymbol of the instrument

exchange

string

Name of the exchange

variety

string

Order variety (regular, amo, co etc.)

product

string

Margin product to use for the order (margins are blocked based on this)
?

order_type

string

Order type (MARKET, LIMIT etc.)

quantity

int64

Quantity of the order

price

float64

Price at which the order is completed

charges

map

The breakdown of the various charges that will be applied to an order
