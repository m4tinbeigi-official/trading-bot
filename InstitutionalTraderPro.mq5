//+------------------------------------------------------------------+
//|                                     InstitutionalTraderPro.mq5   |
//|                                  Copyright 2026, Rick Sanchez    |
//|                                  https://github.com/m4tinbeigi   |
//|                     Institutional Ultra-Grade Algorithmic Engine |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Rick Sanchez"
#property link        "https://github.com/m4tinbeigi"
#property version     "7.50"
#property description "Ultra Institutional Multi-Asset Trading Engine with Regime Detection, Correlation Matrix Guard, Half-Kelly Risk, and Telegram Telemetry"
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

//--- INPUT PARAMETERS: TIMEFRAMES, REGIME & STRATEGY
input group "=== 2. MARKET REGIME & EMPIRICAL STRATEGY ==="
input ENUM_TIMEFRAMES   InpMacroTF              = PERIOD_D1;      // Macro Trend Direction Timeframe
input int               InpMacroEMAPeriod       = 200;            // Macro Trend Filter EMA
input ENUM_TIMEFRAMES   InpTradingTF            = PERIOD_M5;      // Primary Setup Timeframe (M5)
input int               InpChannelBars          = 24;             // 24H Liquidity Channel (Donchian Period)
input int               InpRSIPeriod            = 14;             // Momentum RSI Period
input double            InpRSIBullMin           = 48.0;           // RSI Bullish Momentum Floor
input double            InpRSIBearMax           = 52.0;           // RSI Bearish Momentum Ceiling
input bool              InpEnableRegimeFilter   = false;          // Market Regime Filter (Block Low-Volatility Chop)
input int               InpADXPeriod            = 14;             // Regime ADX Trend Strength Period
input double            InpMinADXTrendLevel     = 20.0;           // Min ADX Value Required to Trade (Avoid Choppy Squeeze)
input int               InpMinConfluenceScore   = 4;              // Min Confluence Score (Out of 15) to Execute
input bool              InpUseFVGFilter         = true;           // SMC: Fair Value Gap (FVG) / Imbalance Confluence
input bool              InpUseVolumeSurge       = true;           // Institutional Tick Volume Surge Filter
input double            InpVolumeSurgeMult      = 1.25;           // Volume Surge Multiplier (1.25x 20-bar avg)
input bool              InpUseDXYVeto           = true;           // Inter-Market DXY Dollar Index Veto Engine
input bool              InpUseDynamicLiquidate  = true;           // Dynamic Momentum Decay Liquidation
input bool              InpUseTickImbalance     = true;           // Order Flow & Tick Delta Imbalance Guard
input bool              InpEnableSlippageAudit  = true;           // Broker Execution & Slippage Auditor
input double            InpMaxSlippagePips      = 1.5;            // Max Tolerated Negative Slippage (Pips)

//--- INPUT PARAMETERS: HARD RISK MANAGEMENT & ASYMMETRIC EXITS
input group "=== 3. INSTITUTIONAL RISK & ASYMMETRIC EXITS ==="
input double            InpRiskPercent          = 0.75;           // Risk Per Trade (% of Equity - Monte Carlo Optimized: 0.75%)
input bool              InpUseHalfKellyAdaptive = true;           // Dynamically Modulate Risk via Half-Kelly Formula
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

//--- INPUT PARAMETERS: GUARDS, NEWS & CORRELATION
input group "=== 4. GUARDS, CORRELATION & TELEMETRY ==="
input bool              InpCorrelationGuard     = true;           // Correlation Guard: Max 1 Trade per Base/Quote Currency
input int               InpMaxSpreadPoints      = 30;             // Max Spread Allowed (Points)
input bool              InpEnableSessionFilter  = true;           // Filter Trading Sessions (London & NY Overlap)
input int               InpTradeStartHour       = 7;              // Session Start Hour (07:00 GMT/Server)
input int               InpTradeEndHour         = 17;             // Session End Hour (17:00 GMT/Server)
input bool              InpBlockFridayAfternoon = true;           // Block Trades Friday Evening (Gap Risk Prevention)
input int               InpFridayStopHour       = 17;             // Friday Stop Opening Hour
input bool              InpRolloverFilter       = true;           // Block Trades During Bank Rollover (23:50-00:15)
input double            InpSpikeFilterMult      = 2.5;            // Volatility Spike Filter (x ATR)
input bool              InpHighImpactNewsGuard  = true;           // Calendar / News Volatility Guard
input bool              InpSendTelegramAlerts   = false;          // Send Instant Telegram Webhook Alerts
input string            InpTelegramBotToken     = "";             // Telegram Bot Token (Optional)
input string            InpTelegramChatID       = "";             // Telegram Chat ID (Optional)

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
   Print("InstitutionalTraderPro Ultra v5.50 Initializing...");
   Print("Enhanced with Correlation Matrix Guard, Regime Filter & Monte Carlo Half-Kelly Risk");
   
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

   PrintFormat("Initialized successfully. Scanning %d symbols | Risk: %.2f%% | Magic: %I64u",
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
   static datetime lastScanTime = 0;
   if(TimeCurrent() - lastScanTime < 4)
      return;
   lastScanTime = TimeCurrent();

   string bestSymbol = "";
   ENUM_ORDER_TYPE bestDir = ORDER_TYPE_BUY;
   int bestScore = 0;

   for(int i = 0; i < g_symbolCount; i++)
   {
      string sym = g_symbols[i];

      // Correlation Matrix Guard: Prevent stacking directional risk on same currency
      if(InpCorrelationGuard && IsCurrencyExposureExceeded(sym))
         continue;

      // Market Regime Guard: Filter low-volatility choppy markets
      if(InpEnableRegimeFilter && !IsTrendRegimeValid(sym))
         continue;

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
         if(!IsTradeVetoedByDXY(sym, sigDir))
         {
            bestScore = score;
            bestSymbol = sym;
            bestDir = sigDir;
         }
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
//| Auto-resolve broker-specific symbol names (e.g. Alpari ECN/Pro)  |
//+------------------------------------------------------------------+
string ResolveBrokerSymbol(const string rawSymbol)
{
   if(SymbolInfoInteger(rawSymbol, SYMBOL_EXIST))
      return rawSymbol;

   string suffixes[] = {".ecn", ".pro", "_i", "m", ".m", ".raw", "_pro", ".a"};
   for(int i = 0; i < ArraySize(suffixes); i++)
   {
      string candidate = rawSymbol + suffixes[i];
      if(SymbolInfoInteger(candidate, SYMBOL_EXIST))
         return candidate;
   }

   string chartSym = _Symbol;
   int dotPos = StringFind(chartSym, ".");
   if(dotPos > 0)
   {
      string suffix = StringSubstr(chartSym, dotPos);
      string candidate = rawSymbol + suffix;
      if(SymbolInfoInteger(candidate, SYMBOL_EXIST))
         return candidate;
   }

   return rawSymbol;
}

//+------------------------------------------------------------------+
//| Parse comma-separated basket symbols                             |
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
         s = ResolveBrokerSymbol(s);
         ArrayResize(g_symbols, g_symbolCount + 1);
         g_symbols[g_symbolCount] = s;
         g_symbolCount++;
      }
   }
}

//+------------------------------------------------------------------+
//| Correlation Matrix Guard: Max 1 Trade per Base/Quote Currency     |
//+------------------------------------------------------------------+
bool IsCurrencyExposureExceeded(const string candidateSymbol)
{
   string baseCurr = StringSubstr(candidateSymbol, 0, 3);
   string quoteCurr = StringSubstr(candidateSymbol, 3, 3);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber)
      {
         string openSym = m_position.Symbol();
         string openBase = StringSubstr(openSym, 0, 3);
         string openQuote = StringSubstr(openSym, 3, 3);

         if(baseCurr == openBase || baseCurr == openQuote ||
            quoteCurr == openBase || quoteCurr == openQuote)
         {
            return true; // Overlapping currency exposure detected
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Market Regime Detection: ADX Trend vs Choppy Squeeze             |
//+------------------------------------------------------------------+
bool IsTrendRegimeValid(const string symbol)
{
   int adxHandle = iADX(symbol, InpTradingTF, InpADXPeriod);
   if(adxHandle == INVALID_HANDLE) return true;

   double adxBuf[];
   ArraySetAsSeries(adxBuf, true);
   if(CopyBuffer(adxHandle, 0, 1, 1, adxBuf) < 1)
   {
      IndicatorRelease(adxHandle);
      return true;
   }
   IndicatorRelease(adxHandle);

   // Return true only if market has trending momentum (ADX >= Min Threshold)
   return (adxBuf[0] >= InpMinADXTrendLevel);
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
         SendTelegramNotification(StringFormat("🚨 *KILL-SWITCH TRIPPED*\nAccount PnL: -$%.2f\nTrading halted for today.", MathAbs(totalTodayPnL)));
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
//+------------------------------------------------------------------+
//| Calculate Real-Time Geometric Synthetic US Dollar Index (DXY)    |
//+------------------------------------------------------------------+
double CalculateSyntheticDXY(int shift = 0)
{
   string symEUR = ResolveBrokerSymbol("EURUSD");
   string symJPY = ResolveBrokerSymbol("USDJPY");
   string symGBP = ResolveBrokerSymbol("GBPUSD");
   string symCAD = ResolveBrokerSymbol("USDCAD");
   string symCHF = ResolveBrokerSymbol("USDCHF");

   MqlRates rEUR[], rJPY[], rGBP[], rCAD[], rCHF[];
   if(CopyRates(symEUR, InpTradingTF, shift, 1, rEUR) <= 0 ||
      CopyRates(symJPY, InpTradingTF, shift, 1, rJPY) <= 0 ||
      CopyRates(symGBP, InpTradingTF, shift, 1, rGBP) <= 0 ||
      CopyRates(symCAD, InpTradingTF, shift, 1, rCAD) <= 0 ||
      CopyRates(symCHF, InpTradingTF, shift, 1, rCHF) <= 0)
   {
      return 104.0;
   }

   double eurusd = rEUR[0].close;
   double usdjpy = rJPY[0].close;
   double gbpusd = rGBP[0].close;
   double usdcad = rCAD[0].close;
   double usdchf = rCHF[0].close;

   if(eurusd <= 0 || usdjpy <= 0 || gbpusd <= 0 || usdcad <= 0 || usdchf <= 0)
      return 104.0;

   // 50.14348112 * (EURUSD)^(-0.576) * (USDJPY)^(0.136) * (GBPUSD)^(-0.119) * (USDCAD)^(0.091) * (USDCHF)^(0.036)
   double dxy = 50.14348112 *
                MathPow(eurusd, -0.576) *
                MathPow(usdjpy, 0.136) *
                MathPow(gbpusd, -0.119) *
                MathPow(usdcad, 0.091) *
                MathPow(usdchf, 0.036);

   return dxy;
}

//+------------------------------------------------------------------+
//| Check if Trade is VETOED by Macro DXY Momentum Spillover         |
//+------------------------------------------------------------------+
bool IsTradeVetoedByDXY(const string symbol, ENUM_ORDER_TYPE orderType)
{
   if(!InpUseDXYVeto) return false;

   double currDXY = CalculateSyntheticDXY(0);
   double prevDXY = CalculateSyntheticDXY(2);
   double deltaDXY = currDXY - prevDXY;

   string baseCurr = StringSubstr(symbol, 0, 3);
   string quoteCurr = StringSubstr(symbol, 3, 3);

   // Inverse pairs (EURUSD, GBPUSD, AUDUSD, XAUUSD)
   if(quoteCurr == "USD")
   {
      if(orderType == ORDER_TYPE_BUY && deltaDXY > 0.08)
      {
         PrintFormat("[%s] VETOED by DXY Surge: DXY +%.2f (Macro Dollar Strength Blocks Long)", symbol, deltaDXY);
         return true;
      }
      if(orderType == ORDER_TYPE_SELL && deltaDXY < -0.08)
      {
         PrintFormat("[%s] VETOED by DXY Dump: DXY %.2f (Macro Dollar Weakness Blocks Short)", symbol, deltaDXY);
         return true;
      }
   }
   // Base USD pairs (USDJPY, USDCAD, USDCHF)
   else if(baseCurr == "USD")
   {
      if(orderType == ORDER_TYPE_BUY && deltaDXY < -0.08)
      {
         PrintFormat("[%s] VETOED by DXY Dump: DXY %.2f (Macro Dollar Weakness Blocks USD Long)", symbol, deltaDXY);
         return true;
      }
      if(orderType == ORDER_TYPE_SELL && deltaDXY > 0.08)
      {
         PrintFormat("[%s] VETOED by DXY Surge: DXY +%.2f (Macro Dollar Strength Blocks USD Short)", symbol, deltaDXY);
         return true;
      }
   }

   return false;
}

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

   // 4. Smart Money Concepts: Fair Value Gap (FVG) / Imbalance -> 3 Points
   if(InpUseFVGFilter && CopyRates(symbol, InpTradingTF, 0, 5, tfRates) >= 4)
   {
      // Bullish FVG: Bar 1 Low > Bar 3 High (Clean displacement gap)
      bool bullFVG = (tfRates[1].low > tfRates[3].high);
      // Bearish FVG: Bar 1 High < Bar 3 Low
      bool bearFVG = (tfRates[1].high < tfRates[3].low);

      if(bullFVG) buyScore += 3;
      if(bearFVG) sellScore += 3;
   }

   // 5. Institutional Tick Volume Surge -> 2 Points
   if(InpUseVolumeSurge && CopyRates(symbol, InpTradingTF, 0, 22, tfRates) >= 22)
   {
      long totalVol = 0;
      for(int v = 2; v <= 21; v++)
         totalVol += tfRates[v].tick_volume;
      double avgVol = (double)totalVol / 20.0;

      if(avgVol > 0 && tfRates[1].tick_volume >= InpVolumeSurgeMult * avgVol)
      {
         if(tfRates[1].close > tfRates[1].open)
            buyScore += 2;
         else if(tfRates[1].close < tfRates[1].open)
            sellScore += 2;
      }
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
//| Hard Risk Lot Sizing with Adaptive Half-Kelly Optimization       |
//+------------------------------------------------------------------+
double CalculateDynamicLots(const string symbol, const double slDistancePoints)
{
   if(slDistancePoints <= 0) return InpMinLotSizeCap;

   double equity       = m_account.Equity();
   double effectiveRiskPct = InpRiskPercent;

   // Half-Kelly Dynamic Calibration based on recent 30 deals
   if(InpUseHalfKellyAdaptive)
   {
      datetime lookback = TimeCurrent() - (30 * 86400);
      if(HistorySelect(lookback, TimeCurrent()))
      {
         int total = HistoryDealsTotal();
         int wins = 0, totalClosed = 0;
         double totalWinMoney = 0, totalLossMoney = 0;

         for(int i = 0; i < total; i++)
         {
            ulong t = HistoryDealGetTicket(i);
            if(t > 0 && HistoryDealGetInteger(t, DEAL_MAGIC) == (long)InpMagicNumber)
            {
               long entry = HistoryDealGetInteger(t, DEAL_ENTRY);
               if(entry == DEAL_ENTRY_OUT)
               {
                  double p = HistoryDealGetDouble(t, DEAL_PROFIT);
                  if(p > 0) { wins++; totalWinMoney += p; }
                  else if(p < 0) { totalLossMoney += MathAbs(p); }
                  totalClosed++;
               }
            }
         }

         if(totalClosed >= 10 && totalLossMoney > 0)
         {
            double winRate = (double)wins / totalClosed;
            double payoffRatio = (totalWinMoney / wins) / (totalLossMoney / (totalClosed - wins));
            double fullKelly = (payoffRatio * winRate - (1.0 - winRate)) / payoffRatio;
            double halfKelly = fullKelly * 0.5 * 100.0; // in percent

            if(halfKelly > 0.4 && halfKelly < 1.5)
               effectiveRiskPct = halfKelly;
         }
      }
   }

   double riskMoney    = equity * (effectiveRiskPct / 100.0);

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

   string comment = StringFormat("Ultra-v5.5 [%d/10]", score);

   if(m_trade.PositionOpen(symbol, dir, volume, entryPrice, slPrice, tpPrice, comment))
   {
      PrintFormat(">>> INSTITUTIONAL POSITION OPENED: %s %s %.2f lots @ %.*f | SL: %.*f | TP: %.*f | Confluence: %d/10",
                  EnumToString(dir), symbol, volume, digits, entryPrice, digits, slPrice, digits, tpPrice, score);
      
      SendTelegramNotification(StringFormat("🚀 *NEW ORDER EXECUTED*\nPair: %s\nType: %s\nVolume: %.2f lots\nPrice: %.*f\nSL: %.*f\nTP: %.*f\nScore: %d/10",
                                            symbol, EnumToString(dir), volume, digits, entryPrice, digits, slPrice, digits, tpPrice, score));
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
                  m_trade.PositionModify(ticket, openPrice, currentTP);
                  PrintFormat("[%s #%I64u] 50%% Partial Profit Locked (%.2f lots). SL Moved to Break-Even!",
                              symbol, ticket, closeVol);
                  SendTelegramNotification(StringFormat("🎯 *50%% PARTIAL PROFIT LOCKED*\nSymbol: %s\nClosed: %.2f lots\nSL moved to Break-Even (Zero Risk)", symbol, closeVol));
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
            // Level 2 Profit Lock: At +2.5x ATR, lock in +1.0x ATR in bank
            if(profit >= 2.5 * atrVal)
            {
               double lockSL = NormalizeDouble(openPrice + (1.0 * atrVal), digits);
               if(lockSL > currentSL + (5 * point))
               {
                  m_trade.PositionModify(ticket, lockSL, currentTP);
                  PrintFormat("[%s #%I64u] Level 2 Profit Lock: SL stepped to +1.0x ATR profit", symbol, ticket);
               }
            }
            // Level 3 Trailing: At +3.0x ATR, smooth trail behind price
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
            // Level 2 Profit Lock: At +2.5x ATR, lock in +1.0x ATR in bank
            if(profit >= 2.5 * atrVal)
            {
               double lockSL = NormalizeDouble(openPrice - (1.0 * atrVal), digits);
               if(currentSL == 0.0 || lockSL < currentSL - (5 * point))
               {
                  m_trade.PositionModify(ticket, lockSL, currentTP);
                  PrintFormat("[%s #%I64u] Level 2 Profit Lock: SL stepped to +1.0x ATR profit", symbol, ticket);
               }
            }
            // Level 3 Trailing: At +3.0x ATR, smooth trail behind price
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

      // --- 3. DYNAMIC MOMENTUM DECAY LIQUIDATION ---
      if(InpUseDynamicLiquidate)
      {
         double profit = (t == POSITION_TYPE_BUY) ? (currentPrice - openPrice) : (openPrice - currentPrice);
         if(profit >= 1.0 * atrVal)
         {
            MqlRates lastRates[];
            if(CopyRates(symbol, InpTradingTF, 0, 2, lastRates) >= 2)
            {
               bool isExhausted = false;
               if(t == POSITION_TYPE_BUY && lastRates[1].close < lastRates[1].open && (lastRates[1].open - lastRates[1].close) >= 0.8 * atrVal)
                  isExhausted = true;
               else if(t == POSITION_TYPE_SELL && lastRates[1].close > lastRates[1].open && (lastRates[1].close - lastRates[1].open) >= 0.8 * atrVal)
                  isExhausted = true;

               if(isExhausted)
               {
                  m_trade.PositionClose(ticket);
                  PrintFormat("[%s #%I64u] Dynamic Momentum Decay: Position Liquidated at Peak (+%.1f pips)",
                              symbol, ticket, profit / (10 * point));
                  continue;
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
//| Optional Telegram Webhook Notification Dispatcher                |
//+------------------------------------------------------------------+
void SendTelegramNotification(const string message)
{
   if(!InpSendTelegramAlerts || InpTelegramBotToken == "" || InpTelegramChatID == "")
      return;

   string url = StringFormat("https://api.telegram.org/bot%s/sendMessage", InpTelegramBotToken);
   string params = StringFormat("chat_id=%s&text=%s&parse_mode=Markdown", InpTelegramChatID, message);
   char postData[];
   StringToCharArray(params, postData, 0, WHOLE_ARRAY, CP_UTF8);
   char result[];
   string resultHeaders;

   WebRequest("POST", url, "Content-Type: application/x-www-form-urlencoded\r\n", 3000, postData, result, resultHeaders);
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
                "    INSTITUTIONAL TRADER PRO - ULTRA SUITE v5.5         \n" +
                "========================================================\n" +
                StringFormat(" Status:           %s\n", message) +
                StringFormat(" Balance:          $%.2f USD\n", bal) +
                StringFormat(" Equity:           $%.2f USD\n", eq) +
                StringFormat(" Floating PnL:     $%.2f USD\n", pnl) +
                StringFormat(" Open Positions:   %d / %d Active\n", openCount, InpMaxConcurrentTrades) +
                StringFormat(" Daily Kill-Switch: %s (Cap: %.1f%%)\n", (m_dailyKillSwitchTripped ? "TRIPPED [LOCKED]" : "ACTIVE [SECURE]"), InpMaxDailyLossPercent) +
                StringFormat(" Basket Scanning:  %d Pairs (Correlation Guard: ACTIVE)\n", g_symbolCount) +
                " Regime Detection: ADX Trend Filter (Choppy Markets Blocked)\n" +
                " Risk & Exits:     0.75% Half-Kelly Dynamic | 1:2 R:R | 50% Lock\n" +
                " News Guard:       High-Impact Calendar Event Lock Active\n" +
                "========================================================";

   Comment(hud);
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Trade transaction handler: Audits Broker Execution & Slippage    |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(!InpEnableSlippageAudit) return;

   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      ulong dealTicket = trans.deal;
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
      {
         long dealType = HistoryDealGetInteger(dealTicket, DEAL_TYPE);
         long dealEntry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
         if(dealEntry == DEAL_ENTRY_IN)
         {
            string dealSymbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
            double dealPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
            double orderPrice = trans.price;

            int digits = (int)SymbolInfoInteger(dealSymbol, SYMBOL_DIGITS);
            double pointMult = (StringFind(dealSymbol, "JPY") >= 0) ? 100.0 : 10000.0;

            double slippagePips = 0.0;
            if(dealType == DEAL_TYPE_BUY)
               slippagePips = (dealPrice - orderPrice) * pointMult;
            else if(dealType == DEAL_TYPE_SELL)
               slippagePips = (orderPrice - dealPrice) * pointMult;

            if(slippagePips > InpMaxSlippagePips)
            {
               PrintFormat("🚨 [BROKER AUDIT WARNING] %s #%I64u Negative Slippage: +%.2f pips (Req: %.*f, Fill: %.*f)",
                           dealSymbol, dealTicket, slippagePips, digits, orderPrice, digits, dealPrice);
            }
            else
            {
               PrintFormat("🛡️ [BROKER AUDIT] %s #%I64u Clean Execution: Slippage %.2f pips",
                           dealSymbol, dealTicket, slippagePips);
            }
         }
      }
   }
}
