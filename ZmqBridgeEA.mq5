//+------------------------------------------------------------------+
//|                                                  ZmqBridgeEA.mq5 |
//|                             Rick Sanchez Autonomous Trading Bot |
//|                                      https://github.com/m4tinbeigi |
//+------------------------------------------------------------------+
#property copyright "Rick Sanchez Trading Bot"
#property link      "https://github.com/m4tinbeigi"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;

// Inputs
input int      InpPort         = 5555;             // Server Port for Python Bridge
input string   InpBindAddress  = "127.0.0.1";      // Localhost IP
input ulong    InpMagicNumber  = 880024;           // Bot Magic Number
input int      InpSlippage     = 10;               // Maximum Slippage in Points

int g_server_socket = INVALID_HANDLE;
int g_client_socket = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpSlippage);
   m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   Print("🟢 Initializing Rick Sanchez Bridge EA on ", InpBindAddress, ":", InpPort);
   
   // Create non-blocking server socket for direct native IPC without DLLs
   g_server_socket = SocketCreate();
   if(g_server_socket == INVALID_HANDLE)
   {
      Print("⚠️ SocketCreate failed, error: ", GetLastError(), ". Running in Terminal Mode.");
   }
   else
   {
      if(SocketBind(g_server_socket, InpBindAddress, InpPort))
      {
         SocketListen(g_server_socket, 5);
         Print("✅ Bridge EA listening on port ", InpPort);
      }
   }
   
   EventSetMillisecondTimer(100); // 100ms polling for responsive order routing
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_client_socket != INVALID_HANDLE) SocketClose(g_client_socket);
   if(g_server_socket != INVALID_HANDLE) SocketClose(g_server_socket);
   Print("🔴 Bridge EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Process incoming JSON command from Python                        |
//+------------------------------------------------------------------+
string ProcessCommand(string json_request)
{
   // 1. PING Command
   if(StringFind(json_request, "\"action\": \"PING\"") >= 0 || StringFind(json_request, "\"PING\"") >= 0)
   {
      return "{\"status\": \"OK\", \"msg\": \"PONG\", \"terminal\": \"MT5\"}";
   }
   
   // 2. ACCOUNT_INFO Command
   if(StringFind(json_request, "\"ACCOUNT_INFO\"") >= 0)
   {
      double balance  = m_account.Balance();
      double equity   = m_account.Equity();
      double margin   = m_account.Margin();
      double free_mg  = m_account.FreeMargin();
      long   leverage = m_account.Leverage();
      string curr     = m_account.Currency();
      
      string resp = StringFormat("{\"status\": \"OK\", \"data\": {\"balance\": %.2f, \"equity\": %.2f, \"margin\": %.2f, \"margin_free\": %.2f, \"leverage\": %d, \"currency\": \"%s\"}}",
                                 balance, equity, margin, free_mg, leverage, curr);
      return resp;
   }
   
   // 3. GET_POSITIONS Command
   if(StringFind(json_request, "\"GET_POSITIONS\"") >= 0)
   {
      string pos_json = "[";
      int total = PositionsTotal();
      int count = 0;
      for(int i = 0; i < total; i++)
      {
         if(m_position.SelectByIndex(i))
         {
            if(count > 0) pos_json += ",";
            string type_str = (m_position.PositionType() == POSITION_TYPE_BUY) ? "BUY" : "SELL";
            pos_json += StringFormat("{\"ticket\": %d, \"symbol\": \"%s\", \"side\": \"%s\", \"volume\": %.2f, \"entry_price\": %.5f, \"stop_loss\": %.5f, \"take_profit\": %.5f, \"profit\": %.2f}",
                                     m_position.Ticket(), m_position.Symbol(), type_str, m_position.Volume(), m_position.PriceOpen(), m_position.StopLoss(), m_position.TakeProfit(), m_position.Profit());
            count++;
         }
      }
      pos_json += "]";
      return StringFormat("{\"status\": \"OK\", \"data\": %s}", pos_json);
   }
   
   // 4. ORDER_CLOSE_ALL Command
   if(StringFind(json_request, "\"ORDER_CLOSE_ALL\"") >= 0)
   {
      int total = PositionsTotal();
      for(int i = total - 1; i >= 0; i--)
      {
         if(m_position.SelectByIndex(i))
         {
            m_trade.PositionClose(m_position.Ticket());
         }
      }
      return "{\"status\": \"OK\", \"msg\": \"ALL_CLOSED\"}";
   }
   
   return "{\"status\": \"OK\", \"msg\": \"COMMAND_ACK\"}";
}

//+------------------------------------------------------------------+
//| Timer event: check incoming socket requests                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(g_server_socket == INVALID_HANDLE) return;
   
   uint len = SocketIsReadable(g_server_socket);
   if(len > 0)
   {
      int client = SocketAccept(g_server_socket);
      if(client != INVALID_HANDLE)
      {
         uchar req_buf[2048];
         int bytes = SocketRead(client, req_buf, sizeof(req_buf), 200);
         if(bytes > 0)
         {
            string req = CharArrayToString(req_buf, 0, bytes);
            string resp = ProcessCommand(req);
            uchar resp_buf[];
            StringToCharArray(resp, resp_buf);
            SocketSend(client, resp_buf, ArraySize(resp_buf) - 1);
         }
         SocketClose(client);
      }
   }
}

void OnTick()
{
   // Live tick handler
}
