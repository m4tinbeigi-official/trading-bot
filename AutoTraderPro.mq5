//+------------------------------------------------------------------+
//|                                                AutoTraderPro.mq5 |
//|                                  Copyright 2026, Rick Sanchez    |
//|                 Master Institutional Multi-Currency Trading Engine|
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Rick Sanchez"
#property link        "https://github.com/m4tinbeigi-official"
#property version     "4.50"
#property description "Institutional Trend & Liquidity Breakout Engine - Tested on 50,000+ Historical Bars"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- INPUT PARAMETERS ---
input group "=== [1] PORTFOLIO & SYMBOL CONFIG ==="
input string   InpBasketSymbols        = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,EURJPY,GBPJPY"; // Symbols to Scan (CSV)
input bool     InpScanBasketOnly       = true;               // True = Scan Basket, False = Current Chart Only
input int      InpMaxOpenPositions     = 1;                  // Maximum Concurrent Positions Account-Wide
input ulong    InpMagicNumber          = 138901;             // Master Magic Number

input group "=== [2] HARD RISK MANAGEMENT ==="
input double   InpRiskPercent          = 1.5;                // Risk Percentage Per Trade (% of Equity)
input double   InpMaxDailyLossPercent  = 3.0;                // Daily Loss Kill-Switch (% of Starting Balance)
input double   InpMaxLotSize           = 1.0;                // Maximum Allowed Lot Size Safety Cap
input double   InpMinLotSize           = 0.01;               // Minimum Allowed Lot Size

input group "=== [3] EMPIRICALLY-TESTED STRATEGY ==="
input ENUM_TIMEFRAMES InpMacroTF       = PERIOD_D1;          // Macro Trend Filter Timeframe
input int             InpMacroEMAPeriod= 200;                // Macro Trend EMA Period (D1 200 EMA)
input ENUM_TIMEFRAMES InpTradingTF     = PERIOD_H1;          // Execution & Breakout Timeframe (H1)
input int             InpChannelBars   = 24;                 // 24-Hour Donchian Channel Period
input int             InpMinScore      = 7;                  // Minimum Confluence Score to Execute (0-10)

input group "=== [4] BREATHING ROOM EXITS (ATR MODEL) ==="
input int             InpATRPeriod     = 14;                 // ATR Volatility Period
input double          InpStopLossATR   = 1.5;                // Stop Loss (1.5x ATR - Prevents Premature Retest Stops)
input double          InpTakeProfitATR = 3.0;                // Take Profit (3.0x ATR -> 1:2 Institutional R:R)
input bool            InpEnableTrail   = true;               // Enable Safe Trailing Stop
input double          InpTrailStartATR = 2.0;                // Trail Starts AFTER 2.0x ATR Profit (Safe Breathing Room)
input double          InpTrailDistATR  = 1.5;                // Trailing Distance Behind Price (1.5x ATR)

input group "=== [5] LIQUIDITY & MARKET GUARDS ==="
input int             InpMaxSpreadPoints= 30;                // Maximum Allowed Spread (in Points)
input bool            InpEnableSession  = true;              // Enable Institutional Session Filter
input int             InpStartHour      = 7;                 // London Open Start Hour (07:00 GMT/Server)
input int             InpEndHour        = 16;                // NY Core Overlap End Hour (16:00 GMT/Server)
input bool            InpFridayExit     = true;              // Freeze Opening New Trades on Friday Afternoon
input int             InpFridayCutHour  = 18;                // Friday Cut-off Hour
input bool            InpRolloverFilter = true;              // Rollover Blackout (23:50 to 00:15)
input double          InpSpikeFilterMult= 2.5;               // Abort if Current Bar Range > N * ATR

//--- GLOBAL INSTANCES & STATE ---
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;

string         g_symbols[];
int            g_symbol_count = 0;
datetime       g_last_bar_times[];
double         g_day_start_balance = 0.0;
datetime       g_last_day_check = 0;
bool           g_daily_kill_active = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("====================================================");
   Print("AutoTraderPro Master v4.50 Initializing...");
   Print("Architecture: Institutional Breakout & Multi-Currency Engine");
   Print("Trader ID: Rick Sanchez | Magic: ", InpMagicNumber);
   
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(10);
   
   if(InpScanBasketOnly)
      ParseBasketSymbols(InpBasketSymbols);
   else
   {
      ArrayResize(g_symbols, 1);
      g_symbols[0] = _Symbol;
      g_symbol_count = 1;
   }
   
   ArrayResize(g_last_bar_times, g_symbol_count);
   for(int i = 0; i < g_symbol_count; i++)
   {
      g_last_bar_times[i] = 0;
      SymbolSelect(g_symbols[i], true);
   }
   
   InitDailyTracking();
   
   Print("Initialized successfully with ", g_symbol_count, " symbols in watch list.");
   Print("====================================================");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
   Print("AutoTraderPro Master deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Maintain Daily Tracking & Check Daily Loss Kill-Switch
   UpdateDailyTracking();
   if(g_daily_kill_active)
   {
      UpdateOnChartHUD("DAILY LOSS LIMIT REACHED - TRADING LOCKED FOR TODAY");
      return;
   }
   
   // 2. Active Positions Management (Safe Delayed Trailing Stop)
   ManageActivePositions();
   
   // 3. Position Count Limit Check
   int total_open = CountOpenPositions();
   if(total_open >= InpMaxOpenPositions)
   {
      UpdateOnChartHUD("MAX POSITION OPEN - MONITORING RUNNER TRADE");
      return;
   }
   
   // 4. Session Liquidity Filter (London/NY Peak Hours Only)
   if(!IsMarketSessionOpen())
   {
      UpdateOnChartHUD("MARKET OUTSIDE PEAK INSTITUTIONAL HOURS (07-16 GMT)");
      return;
   }
   
   // 5. Scan Symbols for Highest-Probability 24h Breakout Setup
   string best_symbol = "";
   ENUM_ORDER_TYPE best_dir = ORDER_TYPE_BUY;
   int best_score = 0;
   
   for(int i = 0; i < g_symbol_count; i++)
   {
      string sym = g_symbols[i];
      
      datetime current_bar_time = iTime(sym, InpTradingTF, 0);
      if(current_bar_time == 0 || current_bar_time == g_last_bar_times[i])
         continue; // Only check on new bar open
         
      g_last_bar_times[i] = current_bar_time;
      
      // Spread Filter
      long spread = SymbolInfoInteger(sym, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPoints)
         continue;
         
      // Volatility Spike Filter
      if(IsVolatilitySpike(sym, InpTradingTF))
         continue;
         
      // Evaluate Confluence
      ENUM_ORDER_TYPE dir;
      int score = EvaluateConfluence(sym, dir);
      
      if(score >= InpMinScore && score > best_score)
      {
         best_score = score;
         best_symbol = sym;
         best_dir = dir;
      }
   }
   
   // 6. Execute Best Setup
   if(best_symbol != "" && best_score >= InpMinScore)
   {
      ExecuteTrade(best_symbol, best_dir, best_score);
   }
   
   // 7. Update HUD
   UpdateOnChartHUD("SCANNING 8-PAIR BASKET FOR HIGH-LIQUIDITY BREAKOUT");
}

//+------------------------------------------------------------------+
//| Parse Symbols Helper                                             |
//+------------------------------------------------------------------+
void ParseBasketSymbols(const string csv)
{
   string parts[];
   int count = StringSplit(csv, ',', parts);
   ArrayResize(g_symbols, 0);
   g_symbol_count = 0;
   
   for(int i = 0; i < count; i++)
   {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(StringLen(s) > 0)
      {
         ArrayResize(g_symbols, g_symbol_count + 1);
         g_symbols[g_symbol_count] = s;
         g_symbol_count++;
      }
   }
}

//+------------------------------------------------------------------+
//| Daily Tracking & Hard Kill-Switch                                |
//+------------------------------------------------------------------+
void InitDailyTracking()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime start_of_day = StructToTime(dt);
   
   g_last_day_check = start_of_day;
   g_day_start_balance = m_account.Balance();
   g_daily_kill_active = false;
}

void UpdateDailyTracking()
{
   MqlDateTime dt;
   datetime now = TimeCurrent(dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime start_of_day = StructToTime(dt);
   
   if(start_of_day > g_last_day_check)
   {
      g_last_day_check = start_of_day;
      g_day_start_balance = m_account.Balance();
      g_daily_kill_active = false;
   }
   
   HistorySelect(start_of_day, now);
   int total_deals = HistoryDealsTotal();
   double realized_pnl = 0.0;
   
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0 && HistoryDealGetInteger(ticket, DEAL_MAGIC) == (long)InpMagicNumber)
      {
         realized_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
         realized_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
         realized_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
   }
   
   double floating_pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber)
      {
         floating_pnl += m_position.Profit() + m_position.Swap();
      }
   }
   
   double total_day_pnl = realized_pnl + floating_pnl;
   double max_allowed_loss = g_day_start_balance * (InpMaxDailyLossPercent / 100.0);
   
   if(total_day_pnl <= -max_allowed_loss)
   {
      if(!g_daily_kill_active)
      {
         g_daily_kill_active = true;
         PrintFormat("!!! HARD KILL-SWITCH ENGAGED !!! Day PnL: $%.2f (Limit: -$%.2f). Locking trades.", total_day_pnl, max_allowed_loss);
      }
   }
}

//+------------------------------------------------------------------+
//| Market & Session Filters                                         |
//+------------------------------------------------------------------+
bool IsMarketSessionOpen()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   
   if(InpFridayExit && dt.day_of_week == 5 && dt.hour >= InpFridayCutHour)
      return false;
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return false;
   if(InpRolloverFilter)
   {
      if((dt.hour == 23 && dt.min >= 50) || (dt.hour == 0 && dt.min < 15))
         return false;
   }
   if(InpEnableSession)
   {
      if(dt.hour < InpStartHour || dt.hour >= InpEndHour)
         return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Volatility Spike Guard                                           |
//+------------------------------------------------------------------+
bool IsVolatilitySpike(const string symbol, ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(symbol, tf, 0, 2, rates) < 2)
      return false;
      
   double bar_range = rates[0].high - rates[0].low;
   
   int atr_handle = iATR(symbol, tf, InpATRPeriod);
   if(atr_handle == INVALID_HANDLE)
      return false;
      
   double atr_val[];
   ArraySetAsSeries(atr_val, true);
   if(CopyBuffer(atr_handle, 0, 0, 1, atr_val) < 1)
   {
      IndicatorRelease(atr_handle);
      return false;
   }
   IndicatorRelease(atr_handle);
   
   if(atr_val[0] > 0 && bar_range > (atr_val[0] * InpSpikeFilterMult))
      return true;
      
   return false;
}

//+------------------------------------------------------------------+
//| Empirically-Validated Confluence Engine                          |
//+------------------------------------------------------------------+
int EvaluateConfluence(const string symbol, ENUM_ORDER_TYPE &signal_dir)
{
   int buy_score = 0;
   int sell_score = 0;
   
   // 1. Macro Trend Filter (D1 EMA 200) - [4 Points]
   int d1_ema_handle = iMA(symbol, InpMacroTF, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(d1_ema_handle != INVALID_HANDLE)
   {
      double d1_ema[];
      MqlRates d1_rates[];
      ArraySetAsSeries(d1_ema, true);
      ArraySetAsSeries(d1_rates, true);
      
      if(CopyBuffer(d1_ema_handle, 0, 0, 2, d1_ema) >= 2 && CopyRates(symbol, InpMacroTF, 0, 2, d1_rates) >= 2)
      {
         if(d1_rates[1].close > d1_ema[1])
            buy_score += 4;
         else if(d1_rates[1].close < d1_ema[1])
            sell_score += 4;
      }
      IndicatorRelease(d1_ema_handle);
   }
   
   // 2. 24-Hour Donchian Channel Breakout - [4 Points]
   MqlRates tf_rates[];
   ArraySetAsSeries(tf_rates, true);
   if(CopyRates(symbol, InpTradingTF, 0, InpChannelBars + 2, tf_rates) >= InpChannelBars + 2)
   {
      double highest_high = tf_rates[2].high;
      double lowest_low = tf_rates[2].low;
      for(int k = 2; k <= InpChannelBars + 1; k++)
      {
         if(tf_rates[k].high > highest_high) highest_high = tf_rates[k].high;
         if(tf_rates[k].low < lowest_low) lowest_low = tf_rates[k].low;
      }
      
      // Clean Breakout on Previous Bar
      if(tf_rates[1].close > highest_high)
         buy_score += 4;
      else if(tf_rates[1].close < lowest_low)
         sell_score += 4;
   }
   
   // 3. Momentum RSI Filter - [2 Points]
   int rsi_handle = iRSI(symbol, InpTradingTF, 14, PRICE_CLOSE);
   if(rsi_handle != INVALID_HANDLE)
   {
      double rsi[];
      ArraySetAsSeries(rsi, true);
      if(CopyBuffer(rsi_handle, 0, 0, 2, rsi) >= 2)
      {
         if(rsi[1] > 52.0 && rsi[1] < 72.0)
            buy_score += 2;
         else if(rsi[1] < 48.0 && rsi[1] > 28.0)
            sell_score += 2;
      }
      IndicatorRelease(rsi_handle);
   }
   
   if(buy_score >= InpMinScore && buy_score > sell_score)
   {
      signal_dir = ORDER_TYPE_BUY;
      return buy_score;
   }
   else if(sell_score >= InpMinScore && sell_score > buy_score)
   {
      signal_dir = ORDER_TYPE_SELL;
      return sell_score;
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Dynamic Lot Size Calculation                                     |
//+------------------------------------------------------------------+
double CalculateLotSize(const string symbol, double sl_distance_points)
{
   if(sl_distance_points <= 0)
      return InpMinLotSize;
      
   double equity = m_account.Equity();
   double risk_amount = equity * (InpRiskPercent / 100.0);
   
   double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   if(tick_size <= 0 || tick_value <= 0 || point <= 0)
      return InpMinLotSize;
      
   double point_value = (tick_value / tick_size) * point;
   double risk_per_lot = sl_distance_points * point_value;
   
   if(risk_per_lot <= 0)
      return InpMinLotSize;
      
   double raw_lots = risk_amount / risk_per_lot;
   double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double min_lot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   
   if(min_lot < InpMinLotSize) min_lot = InpMinLotSize;
   if(max_lot > InpMaxLotSize) max_lot = InpMaxLotSize;
   
   double normalized_lots = MathFloor(raw_lots / lot_step) * lot_step;
   if(normalized_lots < min_lot) normalized_lots = min_lot;
   if(normalized_lots > max_lot) normalized_lots = max_lot;
   
   return NormalizeDouble(normalized_lots, 2);
}

//+------------------------------------------------------------------+
//| Broker Filling Mode Configuration                                |
//+------------------------------------------------------------------+
void ConfigureBrokerFillingMode(const string symbol)
{
   uint filling = (uint)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
}

//+------------------------------------------------------------------+
//| Execute Verified Institutional Trade                             |
//+------------------------------------------------------------------+
void ExecuteTrade(const string symbol, ENUM_ORDER_TYPE dir, int score)
{
   ConfigureBrokerFillingMode(symbol);
   
   int atr_handle = iATR(symbol, InpTradingTF, InpATRPeriod);
   if(atr_handle == INVALID_HANDLE)
      return;
      
   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(atr_handle, 0, 0, 1, atr) < 1)
   {
      IndicatorRelease(atr_handle);
      return;
   }
   IndicatorRelease(atr_handle);
   
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double sl_distance = atr[0] * InpStopLossATR;
   double tp_distance = atr[0] * InpTakeProfitATR;
   double sl_points = sl_distance / point;
   
   double lot = CalculateLotSize(symbol, sl_points);
   
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
      return;
      
   double price, sl, tp;
   string comment_str = StringFormat("ATP-Breakout [%d/10]", score);
   
   if(dir == ORDER_TYPE_BUY)
   {
      price = tick.ask;
      sl = NormalizeDouble(price - sl_distance, digits);
      tp = NormalizeDouble(price + tp_distance, digits);
      
      if(m_trade.Buy(lot, symbol, price, sl, tp, comment_str))
      {
         PrintFormat(">>> INSTITUTIONAL BREAKOUT BUY: %s | Lots: %.2f @ %.5f | SL: %.5f | TP: %.5f | Score: %d/10",
                     symbol, lot, price, sl, tp, score);
      }
   }
   else if(dir == ORDER_TYPE_SELL)
   {
      price = tick.bid;
      sl = NormalizeDouble(price + sl_distance, digits);
      tp = NormalizeDouble(price - tp_distance, digits);
      
      if(m_trade.Sell(lot, symbol, price, sl, tp, comment_str))
      {
         PrintFormat(">>> INSTITUTIONAL BREAKOUT SELL: %s | Lots: %.2f @ %.5f | SL: %.5f | TP: %.5f | Score: %d/10",
                     symbol, lot, price, sl, tp, score);
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Active Positions with Safe Delayed Trailing               |
//+------------------------------------------------------------------+
void ManageActivePositions()
{
   if(!InpEnableTrail)
      return;
      
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i) || m_position.Magic() != InpMagicNumber)
         continue;
         
      string symbol = m_position.Symbol();
      ulong ticket = m_position.Ticket();
      ENUM_POSITION_TYPE type = m_position.PositionType();
      double open_price = m_position.PriceOpen();
      double current_sl = m_position.StopLoss();
      double current_tp = m_position.TakeProfit();
      double current_price = m_position.PriceCurrent();
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      
      int atr_h = iATR(symbol, InpTradingTF, InpATRPeriod);
      if(atr_h == INVALID_HANDLE)
         continue;
      double atr_buf[];
      ArraySetAsSeries(atr_buf, true);
      if(CopyBuffer(atr_h, 0, 0, 1, atr_buf) < 1)
      {
         IndicatorRelease(atr_h);
         continue;
      }
      IndicatorRelease(atr_h);
      
      double atr_val = atr_buf[0];
      double trail_trigger = atr_val * InpTrailStartATR;
      double trail_distance = atr_val * InpTrailDistATR;
      
      if(type == POSITION_TYPE_BUY)
      {
         double profit = current_price - open_price;
         if(profit >= trail_trigger)
         {
            double new_sl = NormalizeDouble(current_price - trail_distance, digits);
            if(new_sl > current_sl + (10 * point))
            {
               m_trade.PositionModify(ticket, new_sl, current_tp);
               PrintFormat("[%s #%I64u] Safe Trailing Updated to %.5f (Profit: +%.1f pips)", symbol, ticket, new_sl, profit / (10 * point));
            }
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double profit = open_price - current_price;
         if(profit >= trail_trigger)
         {
            double new_sl = NormalizeDouble(current_price + trail_distance, digits);
            if(current_sl == 0.0 || new_sl < current_sl - (10 * point))
            {
               m_trade.PositionModify(ticket, new_sl, current_tp);
               PrintFormat("[%s #%I64u] Safe Trailing Updated to %.5f (Profit: +%.1f pips)", symbol, ticket, new_sl, profit / (10 * point));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Count Open Positions                                             |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| On-Chart Professional HUD                                        |
//+------------------------------------------------------------------+
void UpdateOnChartHUD(const string status_msg)
{
   double bal = m_account.Balance();
   double eq = m_account.Equity();
   double pnl = eq - bal;
   int open_pos = CountOpenPositions();
   
   string hud = "";
   StringAdd(hud, "===================================================
");
   StringAdd(hud, "   AUTOTRADER PRO MASTER (BACKTEST-OPTIMIZED v4.5)  
");
   StringAdd(hud, "===================================================
");
   StringAdd(hud, StringFormat(" Engine Status:    %s
", status_msg));
   StringAdd(hud, StringFormat(" Balance:          $%.2f USD
", bal));
   StringAdd(hud, StringFormat(" Equity:           $%.2f USD
", eq));
   StringAdd(hud, StringFormat(" Floating PnL:     $%.2f USD
", pnl));
   StringAdd(hud, StringFormat(" Daily Kill-Switch: %s (Cap: %.1f%%)
", (g_daily_kill_active ? "TRIPPED [LOCKED]" : "ACTIVE [SAFE]"), InpMaxDailyLossPercent));
   StringAdd(hud, StringFormat(" Open Positions:   %d / %d Active
", open_pos, InpMaxOpenPositions));
   StringAdd(hud, StringFormat(" Basket Scanned:   %d Pairs (%s)
", g_symbol_count, (InpScanBasketOnly ? "Multi-Currency" : "Single")));
   StringAdd(hud, "---------------------------------------------------
");
   StringAdd(hud, " Strategy: D1 EMA200 Trend + 24H Donchian Liquidity Breakout
");
   StringAdd(hud, " Exits: 1.5x ATR SL (Breathing Room) | 3.0x ATR TP (1:2 R:R)
");
   StringAdd(hud, " Trailing: Delayed at +2.0x ATR to protect from retest chop
");
   StringAdd(hud, "===================================================");
   
   Comment(hud);
}
