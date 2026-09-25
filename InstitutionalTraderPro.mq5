//+------------------------------------------------------------------+
//|                                     InstitutionalTraderPro.mq5   |
//|                                  Copyright 2026, Rick Sanchez    |
//|                                  https://github.com/m4tinbeigi   |
//|                     Institutional Ultra-Grade Algorithmic Engine |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Rick Sanchez"
#property link        "https://github.com/m4tinbeigi"
#property version     "5.00"
#property description "Ultra Institutional Multi-Asset Trading Engine with Dynamic Risk, Confluence Scoring, and News Guard"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\DealInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- INPUT PARAMETERS: ARCHITECTURE & PORTFOLIO
input group "=== 1. ARCHITECTURE & PORTFOLIO ==="
input ulong             InpMagicNumber          = 20260901;       // Master Magic Number
input string            InpBasketSymbols        = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,EURJPY,GBPJPY"; // Multi-Currency Basket (CSV)
input bool              InpScanBasketOnly       = true;           // True = Multi-Currency Basket, False = Chart Symbol Only
input int               InpMaxConcurrentTrades  = 2;              // Max Allowed Concurrent Open Positions
input ulong             InpSlippagePoints       = 20;             // Max Execution Deviation (Points)

//--- INPUT PARAMETERS: TIMEFRAMES & STRATEGY
input group "=== 2. EMPIRICAL MULTI-TIMEFRAME STRATEGY ==="
input ENUM_TIMEFRAMES   InpMacroTF              = PERIOD_D1;      // Macro Trend Direction Timeframe
input int               InpMacroEMAPeriod       = 200;            // Macro Trend Filter EMA
input ENUM_TIMEFRAMES   InpTradingTF            = PERIOD_H1;      // Primary Setup Timeframe (H1)
input int               InpChannelBars          = 24;             // 24H Liquidity Channel (Donchian Period)
input int               InpRSIPeriod            = 14;             // Momentum RSI Period
input double            InpRSIBullMin           = 48.0;           // RSI Bullish Momentum Floor
input double            InpRSIBearMax           = 52.0;           // RSI Bearish Momentum Ceiling
input int               InpMinConfluenceScore   = 7;              // Min Institutional Confluence Score (0-10)

//--- INPUT PARAMETERS: HARD RISK MANAGEMENT & ASYMMETRIC EXITS
input group "=== 3. INSTITUTIONAL RISK & ASYMMETRIC EXITS ==="
input double            InpRiskPercent          = 1.5;            // Risk Per Trade (% of Account Equity)
input double            InpMaxDailyLossPercent  = 3.0;            // Daily Drawdown Hard Kill-Switch (%)
input double            InpMinLotSizeCap        = 0.01;           // Minimum Lot Size Cap
input double            InpMaxLotSizeCap        = 1.00;           // Maximum Lot Size Cap
input int               InpATRPeriod            = 14;             // Market Volatility Period (ATR)
input double            InpSL_ATR_Mult          = 1.5;            // Stop Loss Distance (x ATR - Retest Breathing Room)
input double            InpTP_ATR_Mult          = 3.0;            // Take Profit Distance (x ATR -> Strict 1:2 R:R)
input bool              InpEnablePartialClose   = true;           // Enable 50% Partial Take Profit at +1.5x ATR
input double            InpPartialCloseATR      = 1.5;            // Partial Take Profit Target (x ATR)
input bool              InpEnableTrailing       = true;           // Enable Dynamic Trailing Stop
input double            InpTrailStartATR        = 2.0;            // Trailing Starts AFTER +2.0x ATR Profit
input double            InpTrailDistATR         = 1.5;            // Trailing Buffer Behind Price (x ATR)

//--- INPUT PARAMETERS: GUARDS & NEWS
input group "=== 4. MARKET, SESSION & NEWS GUARDS ==="
input int               InpMaxSpreadPoints      = 30;             // Max Spread Allowed (Points)
input bool              InpEnableSessionFilter  = true;           // Filter Trading Sessions (London & NY Overlap)
input int               InpTradeStartHour       = 7;              // Session Start Hour (07:00 GMT/Server)
input int               InpTradeEndHour         = 17;             // Session End Hour (17:00 GMT/Server)
input bool              InpBlockFridayAfternoon = true;           // Block Trades Friday Evening (Gap Risk Prevention)
input int               InpFridayStopHour       = 17;             // Friday Stop Opening Hour
input bool              InpRolloverFilter       = true;           // Block Trades During Bank Rollover (23:50-00:15)
input double            InpSpikeFilterMult      = 2.5;            // Volatility Spike Filter (x ATR)
input bool              InpHighImpactNewsGuard  = true;           // Calendar / News Volatility Guard

//--- GLOBAL STRUCTURES & STORAGE
struct PositionRecord
{
   ulong    ticket;
   bool     partialTaken;
};

CTrade                  m_trade;
CPositionInfo           m_position;
CDealInfo               m_deal;
CAccountInfo            m_account;

string                  g_symbols[];
int                     g_symbolCount = 0;
datetime                g_lastBarTimes[];
PositionRecord          g_activeRecords[];
int                     g_recordCount = 0;

datetime                m_lastDailyCheckDate    = 0;
double                  m_dayStartBalance       = 0.0;
bool                    m_dailyKillSwitchTripped= false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("========================================================");
   Print("InstitutionalTraderPro Ultra v5.0 Initializing...");
   Print("Institutional Multi-Currency Engine with Empirical Breathing Room");
   
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetDeviationInPoints(InpSlippagePoints);

   if(InpScanBasketOnly)
      ParseBasketSymbols(InpBasketSymbols);
   else
   {
      ArrayResize(g_symbols, 1);
      g_symbols[0] = _Symbol;
      g_symbolCount = 1;
   }

   ArrayResize(g_lastBarTimes, g_symbolCount);
   for(int i = 0; i < g_symbolCount; i++)
   {
      g_lastBarTimes[i] = 0;
      SymbolSelect(g_symbols[i], true);
      ConfigureBrokerFillingMode(g_symbols[i]);
   }

   InitDailyTracking();

   PrintFormat("Initialized successfully. Scanning %d symbols | Risk: %.1f%% | Magic: %I64u",
               g_symbolCount, InpRiskPercent, InpMagicNumber);
   Print("========================================================");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
   Print("InstitutionalTraderPro Ultra deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Maintain Day Balances & Daily Hard Loss Kill-Switch
   UpdateDailyTracking();
   if(m_dailyKillSwitchTripped)
   {
      UpdateStatusHUD("DAILY LOSS KILL-SWITCH ACTIVE - TRADING FROZEN TODAY");
      return;
   }

   // 2. Position Management: Breathing Room Trailing & 50% Partial Take Profit
   ManagePositionsAndExits();

   // 3. Check Max Allowed Concurrent Positions
   int openCount = CountActivePositions();
   if(openCount >= InpMaxConcurrentTrades)
   {
      UpdateStatusHUD(StringFormat("MAX POSITIONS OPEN (%d/%d) - MANAGING RUNNERS", openCount, InpMaxConcurrentTrades));
      return;
   }

   // 4. Session & Market Liquidity Guards
   if(!IsMarketSessionOpen())
   {
      UpdateStatusHUD("MARKET OUTSIDE PEAK INSTITUTIONAL HOURS (07-17 SERVER)");
      return;
   }

   // 5. High-Impact Economic News Calendar Guard
   if(InpHighImpactNewsGuard && IsHighImpactNewsNearby())
   {
      UpdateStatusHUD("NEWS GUARD ACTIVE: HIGH-IMPACT CALENDAR EVENT NEARBY - ENTRY BLOCKED");
      return;
   }

   // 6. Multi-Asset Scanning & Confluence Execution
   string bestSymbol = "";
   ENUM_ORDER_TYPE bestDir = ORDER_TYPE_BUY;
   int bestScore = 0;

   for(int i = 0; i < g_symbolCount; i++)
   {
      string sym = g_symbols[i];

      datetime currentBarTime = iTime(sym, InpTradingTF, 0);
      if(currentBarTime == 0 || currentBarTime == g_lastBarTimes[i])
         continue; // Only process on new bar open

      g_lastBarTimes[i] = currentBarTime;

      // Spread Guard
      long spread = SymbolInfoInteger(sym, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPoints)
         continue;

      // Volatility Spike Guard
      if(IsVolatilitySpike(sym, InpTradingTF))
         continue;

      // Evaluate Strategy Confluence
      ENUM_ORDER_TYPE sigDir;
      int score = EvaluateConfluenceScore(sym, sigDir);

      if(score >= InpMinConfluenceScore && score > bestScore)
      {
         bestScore = score;
         bestSymbol = sym;
         bestDir = sigDir;
      }
   }

   // 7. Execute the Single Highest Confluence Opportunity
   if(bestSymbol != "" && bestScore >= InpMinConfluenceScore)
   {
      ExecuteInstitutionalTrade(bestSymbol, bestDir, bestScore);
   }

   // 8. Update HUD
   UpdateStatusHUD(StringFormat("SCANNING %d-PAIR BASKET FOR HIGH-PROBABILITY CONFLUENCE", g_symbolCount));
}

//+------------------------------------------------------------------+
//| Multi-Asset Basket Parser                                        |
//+------------------------------------------------------------------+
void ParseBasketSymbols(const string csv)
{
   string parts[];
   int count = StringSplit(csv, ',', parts);
   ArrayResize(g_symbols, 0);
   g_symbolCount = 0;

   for(int i = 0; i < count; i++)
   {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(StringLen(s) > 0)
      {
         ArrayResize(g_symbols, g_symbolCount + 1);
         g_symbols[g_symbolCount] = s;
         g_symbolCount++;
      }
   }
}

//+------------------------------------------------------------------+
//| Auto-detect Broker Filling Mode (FOK, IOC, RETURN)               |
//+------------------------------------------------------------------+
void ConfigureBrokerFillingMode(const string symbol)
{
   uint fillingMode = (uint)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);

   if((fillingMode & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fillingMode & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
}

//+------------------------------------------------------------------+
//| Daily Loss Tracking & Hard Kill-Switch                           |
//+------------------------------------------------------------------+
void InitDailyTracking()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   m_lastDailyCheckDate = StructToTime(dt);
   m_dayStartBalance = m_account.Balance();
   m_dailyKillSwitchTripped = false;
}

void UpdateDailyTracking()
{
   MqlDateTime dt;
   datetime now = TimeCurrent(dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime startOfDay = StructToTime(dt);

   if(startOfDay > m_lastDailyCheckDate)
   {
      m_lastDailyCheckDate = startOfDay;
      m_dayStartBalance = m_account.Balance();
      m_dailyKillSwitchTripped = false;
   }

   if(!HistorySelect(startOfDay, now)) return;

   double realizedPnL = 0.0;
   int totalDeals = HistoryDealsTotal();

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0 && HistoryDealGetInteger(ticket, DEAL_MAGIC) == (long)InpMagicNumber)
      {
         long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
         {
            realizedPnL += HistoryDealGetDouble(ticket, DEAL_PROFIT);
            realizedPnL += HistoryDealGetDouble(ticket, DEAL_SWAP);
            realizedPnL += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         }
      }
   }

   double floatingPnL = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber)
      {
         floatingPnL += m_position.Profit() + m_position.Swap();
      }
   }

   double totalTodayPnL = realizedPnL + floatingPnL;
   double maxAllowedLoss = m_dayStartBalance * (InpMaxDailyLossPercent / 100.0);

   if(totalTodayPnL <= -maxAllowedLoss)
   {
      if(!m_dailyKillSwitchTripped)
      {
         m_dailyKillSwitchTripped = true;
         PrintFormat("ALERT: Daily Loss Kill-Switch TRIPPED! PnL: $%.2f <= Max Loss: -$%.2f. All new trading halted.",
                     totalTodayPnL, maxAllowedLoss);
      }
   }
}

//+------------------------------------------------------------------+
//| Market & Session Liquidity Guards                                |
//+------------------------------------------------------------------+
bool IsMarketSessionOpen()
{
   MqlDateTime dt;
   TimeCurrent(dt);

   if(InpBlockFridayAfternoon && dt.day_of_week == 5 && dt.hour >= InpFridayStopHour)
      return false;
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return false;
   if(InpRolloverFilter)
   {
      if((dt.hour == 23 && dt.min >= 50) || (dt.hour == 0 && dt.min <= 15))
         return false;
   }
   if(InpEnableSessionFilter)
   {
      if(dt.hour < InpTradeStartHour || dt.hour >= InpTradeEndHour)
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
   if(CopyRates(symbol, tf, 0, 2, rates) < 2) return false;

   double barRange = rates[0].high - rates[0].low;

   int atrHandle = iATR(symbol, tf, InpATRPeriod);
   if(atrHandle == INVALID_HANDLE) return false;

   double atrVal[];
   ArraySetAsSeries(atrVal, true);
   if(CopyBuffer(atrHandle, 0, 0, 1, atrVal) < 1)
   {
      IndicatorRelease(atrHandle);
      return false;
   }
   IndicatorRelease(atrHandle);

   if(atrVal[0] > 0.0 && barRange > (atrVal[0] * InpSpikeFilterMult))
      return true;

   return false;
}

//+------------------------------------------------------------------+
//| High-Impact News Guard using MQL5 Economic Calendar              |
//+------------------------------------------------------------------+
bool IsHighImpactNewsNearby()
{
   datetime now = TimeCurrent();
   datetime startCheck = now - 1800; // 30 minutes before
   datetime endCheck   = now + 1800; // 30 minutes after

   MqlCalendarValue values[];
   // Check if high impact events are scheduled for USD or EUR
   int count = CalendarValueHistory(values, startCheck, endCheck, NULL, NULL);
   if(count > 0)
   {
      for(int i = 0; i < count; i++)
      {
         MqlCalendarEvent event;
         if(CalendarEventById(values[i].event_id, event))
         {
            if(event.importance == CALENDAR_IMPORTANCE_HIGH)
            {
               return true;
            }
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Empirical Confluence Scoring Engine (0 to 10 Points)             |
//+------------------------------------------------------------------+
int EvaluateConfluenceScore(const string symbol, ENUM_ORDER_TYPE &signalDir)
{
   int buyScore  = 0;
   int sellScore = 0;

   // 1. Macro Trend Direction (D1 EMA 200) -> 4 Points
   int emaHandle = iMA(symbol, InpMacroTF, InpMacroEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(emaHandle != INVALID_HANDLE)
   {
      double emaBuf[];
      MqlRates d1Rates[];
      ArraySetAsSeries(emaBuf, true);
      ArraySetAsSeries(d1Rates, true);

      if(CopyBuffer(emaHandle, 0, 0, 2, emaBuf) >= 2 && CopyRates(symbol, InpMacroTF, 0, 2, d1Rates) >= 2)
      {
         if(d1Rates[1].close > emaBuf[1])
            buyScore += 4;
         else if(d1Rates[1].close < emaBuf[1])
            sellScore += 4;
      }
      IndicatorRelease(emaHandle);
   }

   // 2. 24-Hour Donchian Liquidity Breakout -> 4 Points
   MqlRates tfRates[];
   ArraySetAsSeries(tfRates, true);
   if(CopyRates(symbol, InpTradingTF, 0, InpChannelBars + 2, tfRates) >= InpChannelBars + 2)
   {
      double high24 = tfRates[2].high;
      double low24  = tfRates[2].low;
      for(int k = 2; k <= InpChannelBars + 1; k++)
      {
         if(tfRates[k].high > high24) high24 = tfRates[k].high;
         if(tfRates[k].low < low24)   low24  = tfRates[k].low;
      }

      if(tfRates[1].close > high24)
         buyScore += 4;
      else if(tfRates[1].close < low24)
         sellScore += 4;
   }

   // 3. RSI 14 Momentum Confluence -> 2 Points
   int rsiHandle = iRSI(symbol, InpTradingTF, InpRSIPeriod, PRICE_CLOSE);
   if(rsiHandle != INVALID_HANDLE)
   {
      double rsiBuf[];
      ArraySetAsSeries(rsiBuf, true);
      if(CopyBuffer(rsiHandle, 0, 0, 2, rsiBuf) >= 2)
      {
         if(rsiBuf[1] >= InpRSIBullMin && rsiBuf[1] <= 72.0)
            buyScore += 2;
         else if(rsiBuf[1] <= InpRSIBearMax && rsiBuf[1] >= 28.0)
            sellScore += 2;
      }
      IndicatorRelease(rsiHandle);
   }

   if(buyScore >= InpMinConfluenceScore && buyScore > sellScore)
   {
      signalDir = ORDER_TYPE_BUY;
      return buyScore;
   }
   else if(sellScore >= InpMinConfluenceScore && sellScore > buyScore)
   {
      signalDir = ORDER_TYPE_SELL;
      return sellScore;
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Hard Risk Lot Sizing: Account Equity % / SL Monetary Risk        |
//+------------------------------------------------------------------+
double CalculateDynamicLots(const string symbol, const double slDistancePoints)
{
   if(slDistancePoints <= 0) return InpMinLotSizeCap;

   double equity       = m_account.Equity();
   double riskMoney    = equity * (InpRiskPercent / 100.0);

   double tickSize     = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue    = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double point        = SymbolInfoDouble(symbol, SYMBOL_POINT);

   if(tickSize <= 0.0 || tickValue <= 0.0 || point <= 0.0) return InpMinLotSizeCap;

   double pointValuePerLot = (tickValue / tickSize) * point;
   if(pointValuePerLot <= 0.0) return InpMinLotSizeCap;

   double rawLots = riskMoney / (slDistancePoints * pointValuePerLot);

   double minLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

   if(stepLot <= 0.0) stepLot = 0.01;
   if(minLot < InpMinLotSizeCap) minLot = InpMinLotSizeCap;
   if(maxLot > InpMaxLotSizeCap) maxLot = InpMaxLotSizeCap;

   double normalizedLots = MathFloor(rawLots / stepLot) * stepLot;
   if(normalizedLots < minLot) normalizedLots = minLot;
   if(normalizedLots > maxLot) normalizedLots = maxLot;

   return NormalizeDouble(normalizedLots, 2);
}

//+------------------------------------------------------------------+
//| Execute Institutional Trade with Dynamic Lot Sizing & ATR Exits  |
//+------------------------------------------------------------------+
void ExecuteInstitutionalTrade(const string symbol, ENUM_ORDER_TYPE dir, int score)
{
   ConfigureBrokerFillingMode(symbol);

   int atrHandle = iATR(symbol, InpTradingTF, InpATRPeriod);
   if(atrHandle == INVALID_HANDLE) return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, 0, 1, atrBuf) < 1)
   {
      IndicatorRelease(atrHandle);
      return;
   }
   IndicatorRelease(atrHandle);

   double atr = atrBuf[0];
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits   = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   double slDistance = atr * InpSL_ATR_Mult;
   double tpDistance = atr * InpTP_ATR_Mult;
   double slPoints   = slDistance / point;

   double volume = CalculateDynamicLots(symbol, slPoints);
   if(volume <= 0.0) return;

   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick)) return;

   double entryPrice = (dir == ORDER_TYPE_BUY) ? tick.ask : tick.bid;
   double slPrice = 0.0;
   double tpPrice = 0.0;

   if(dir == ORDER_TYPE_BUY)
   {
      slPrice = NormalizeDouble(entryPrice - slDistance, digits);
      tpPrice = NormalizeDouble(entryPrice + tpDistance, digits);
   }
   else
   {
      slPrice = NormalizeDouble(entryPrice + slDistance, digits);
      tpPrice = NormalizeDouble(entryPrice - tpDistance, digits);
   }

   string comment = StringFormat("Ultra-Breakout [%d/10]", score);

   if(m_trade.PositionOpen(symbol, dir, volume, entryPrice, slPrice, tpPrice, comment))
   {
      PrintFormat(">>> INSTITUTIONAL POSITION OPENED: %s %s %.2f lots @ %.*f | SL: %.*f | TP: %.*f | Confluence: %d/10",
                  EnumToString(dir), symbol, volume, digits, entryPrice, digits, slPrice, digits, tpPrice, score);
   }
   else
   {
      PrintFormat(">>> ORDER EXECUTION FAILED: %s | Error %d - %s",
                  symbol, m_trade.ResultRetcode(), m_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Manage Exits: 50% Partial Take Profit & Safe Delayed Trailing    |
//+------------------------------------------------------------------+
void ManagePositionsAndExits()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!m_position.SelectByIndex(i) || m_position.Magic() != InpMagicNumber)
         continue;

      string symbol        = m_position.Symbol();
      ulong ticket         = m_position.Ticket();
      ENUM_POSITION_TYPE t = m_position.PositionType();
      double openPrice     = m_position.PriceOpen();
      double currentSL     = m_position.StopLoss();
      double currentTP     = m_position.TakeProfit();
      double currentPrice  = m_position.PriceCurrent();
      double volume        = m_position.Volume();
      int digits           = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point         = SymbolInfoDouble(symbol, SYMBOL_POINT);

      int atrHandle = iATR(symbol, InpTradingTF, InpATRPeriod);
      if(atrHandle == INVALID_HANDLE) continue;
      double atrBuf[];
      ArraySetAsSeries(atrBuf, true);
      if(CopyBuffer(atrHandle, 0, 0, 1, atrBuf) < 1)
      {
         IndicatorRelease(atrHandle);
         continue;
      }
      IndicatorRelease(atrHandle);

      double atrVal = atrBuf[0];
      double partialTargetDist = atrVal * InpPartialCloseATR;
      double trailTriggerDist  = atrVal * InpTrailStartATR;
      double trailDistance     = atrVal * InpTrailDistATR;

      bool isPartialDone = GetPartialStatus(ticket);

      // --- 1. 50% PARTIAL TAKE PROFIT AT 1.5x ATR ---
      if(InpEnablePartialClose && !isPartialDone)
      {
         double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
         double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
         double closeVol = NormalizeDouble(MathFloor((volume * 0.5) / step) * step, 2);

         if(closeVol >= minVol && (volume - closeVol) >= minVol)
         {
            if((t == POSITION_TYPE_BUY && (currentPrice - openPrice) >= partialTargetDist) ||
               (t == POSITION_TYPE_SELL && (openPrice - currentPrice) >= partialTargetDist))
            {
               if(m_trade.PositionClosePartial(ticket, closeVol))
               {
                  SetPartialStatus(ticket, true);
                  // Secure Break-Even on remaining half
                  m_trade.PositionModify(ticket, openPrice, currentTP);
                  PrintFormat("[%s #%I64u] 50%% Partial Profit Locked (%.2f lots). SL Moved to Break-Even!",
                              symbol, ticket, closeVol);
               }
            }
         }
      }

      // --- 2. DELAYED SAFE TRAILING STOP AT 2.0x ATR ---
      if(InpEnableTrailing)
      {
         if(t == POSITION_TYPE_BUY)
         {
            double profit = currentPrice - openPrice;
            if(profit >= trailTriggerDist)
            {
               double newSL = NormalizeDouble(currentPrice - trailDistance, digits);
               if(newSL > currentSL + (10 * point))
               {
                  m_trade.PositionModify(ticket, newSL, currentTP);
                  PrintFormat("[%s #%I64u] Trailing Stop Advanced to %.*f (Profit: +%.1f pips)",
                              symbol, ticket, digits, newSL, profit / (10 * point));
               }
            }
         }
         else if(t == POSITION_TYPE_SELL)
         {
            double profit = openPrice - currentPrice;
            if(profit >= trailTriggerDist)
            {
               double newSL = NormalizeDouble(currentPrice + trailDistance, digits);
               if(currentSL == 0.0 || newSL < currentSL - (10 * point))
               {
                  m_trade.PositionModify(ticket, newSL, currentTP);
                  PrintFormat("[%s #%I64u] Trailing Stop Advanced to %.*f (Profit: +%.1f pips)",
                              symbol, ticket, digits, newSL, profit / (10 * point));
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Partial Status Registry                                          |
//+------------------------------------------------------------------+
bool GetPartialStatus(const ulong ticket)
{
   for(int i = 0; i < g_recordCount; i++)
   {
      if(g_activeRecords[i].ticket == ticket)
         return g_activeRecords[i].partialTaken;
   }
   return false;
}

void SetPartialStatus(const ulong ticket, const bool taken)
{
   for(int i = 0; i < g_recordCount; i++)
   {
      if(g_activeRecords[i].ticket == ticket)
      {
         g_activeRecords[i].partialTaken = taken;
         return;
      }
   }
   ArrayResize(g_activeRecords, g_recordCount + 1);
   g_activeRecords[g_recordCount].ticket = ticket;
   g_activeRecords[g_recordCount].partialTaken = taken;
   g_recordCount++;
}

//+------------------------------------------------------------------+
//| Count Active Positions with our Magic Number                     |
//+------------------------------------------------------------------+
int CountActivePositions()
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
//| Sleek Institutional HUD Dashboard                                |
//+------------------------------------------------------------------+
void UpdateStatusHUD(const string message)
{
   double bal = m_account.Balance();
   double eq  = m_account.Equity();
   double pnl = eq - bal;
   int openCount = CountActivePositions();

   string hud = "========================================================\n" +
                "    INSTITUTIONAL TRADER PRO - ULTRA SUITE v5.0         \n" +
                "========================================================\n" +
                StringFormat(" Status:           %s\n", message) +
                StringFormat(" Balance:          $%.2f USD\n", bal) +
                StringFormat(" Equity:           $%.2f USD\n", eq) +
                StringFormat(" Floating PnL:     $%.2f USD\n", pnl) +
                StringFormat(" Open Positions:   %d / %d Active\n", openCount, InpMaxConcurrentTrades) +
                StringFormat(" Daily Kill-Switch: %s (Cap: %.1f%%)\n", (m_dailyKillSwitchTripped ? "TRIPPED [LOCKED]" : "ACTIVE [SECURE]"), InpMaxDailyLossPercent) +
                StringFormat(" Basket Scanning:  %d Pairs (Multi-Currency Portfolio)\n", g_symbolCount) +
                " Confluence Model: D1 EMA200 Trend + 24H Liquidity Breakout + RSI\n" +
                " Risk & Exits:     1.5% Dynamic Equity | 1:2 R:R | 50% Partial Lock\n" +
                " News Guard:       High-Impact Calendar Event Lock Active\n" +
                "========================================================";

   Comment(hud);
}
//+------------------------------------------------------------------+
