export function findCompletedTrades(trades) {
    // Sort trades by timestamp
    const sortedTrades = trades.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    const inventory = {}; // { ticker: [{qty, price, timestamp, side}] }
    const completed = [];

    sortedTrades.forEach(trade => {
        const ticker = trade.ticker;
        if (!inventory[ticker]) inventory[ticker] = [];

        // Determine trade type
        // Actions: "BUY", "SELL", "BUY (COVER)", "SELL (SHORT)", "BUY (ADD)", "SELL (ADD SHORT)"

        const isLongBuy = trade.action.includes('BUY') && !trade.action.includes('COVER');
        const isLongSell = trade.action.includes('SELL') && !trade.action.includes('SHORT');

        const isShortSell = trade.action.includes('SELL') && trade.action.includes('SHORT');
        const isShortCover = trade.action.includes('BUY') && trade.action.includes('COVER');

        if (isLongBuy) {
            // Add to inventory (Long)
            inventory[ticker].push({
                qty: trade.qty,
                price: trade.price,
                timestamp: trade.timestamp,
                side: 'LONG'
            });
        } else if (isShortSell) {
            // Add to inventory (Short)
            inventory[ticker].push({
                qty: trade.qty,
                price: trade.price,
                timestamp: trade.timestamp,
                side: 'SHORT'
            });
        } else if (isLongSell) {
            // Closing Long Position (FIFO)
            let qtyToClose = trade.qty;
            let totalCost = 0;
            let closedQty = 0;
            let firstEntryTime = null;

            // Process inventory
            // We iterate backwards or use a filter? No, FIFO means take from start of array.
            // But we need to filter for 'LONG' side inventory only? 
            // Usually a ticker is either Long or Short, not both simultaneously in this system.

            while (qtyToClose > 0.000001 && inventory[ticker].length > 0) {
                const item = inventory[ticker][0];

                if (item.side !== 'LONG') {
                    // Mismatch side? Should not happen in simple mode, but skip or break
                    break;
                }

                if (!firstEntryTime) firstEntryTime = item.timestamp;

                const takeQty = Math.min(item.qty, qtyToClose);

                totalCost += takeQty * item.price;
                closedQty += takeQty;
                qtyToClose -= takeQty;
                item.qty -= takeQty;

                if (item.qty <= 0.000001) {
                    inventory[ticker].shift(); // Remove empty batch
                }
            }

            if (closedQty > 0) {
                const avgEntryPrice = totalCost / closedQty;
                const pnl = (trade.price - avgEntryPrice) * closedQty;

                completed.push({
                    ticker: ticker,
                    side: 'LONG',
                    entry_time: firstEntryTime || trade.timestamp, // Fallback
                    exit_time: trade.timestamp,
                    entry_price: avgEntryPrice,
                    exit_price: trade.price,
                    qty: closedQty,
                    pnl: pnl
                });
            }

        } else if (isShortCover) {
            // Closing Short Position (FIFO)
            let qtyToCover = trade.qty;
            let totalProceeds = 0;
            let coveredQty = 0;
            let firstEntryTime = null;

            while (qtyToCover > 0.000001 && inventory[ticker].length > 0) {
                const item = inventory[ticker][0];

                if (item.side !== 'SHORT') break;

                if (!firstEntryTime) firstEntryTime = item.timestamp;

                const takeQty = Math.min(item.qty, qtyToCover);

                totalProceeds += takeQty * item.price;
                coveredQty += takeQty;
                qtyToCover -= takeQty;
                item.qty -= takeQty;

                if (item.qty <= 0.000001) {
                    inventory[ticker].shift();
                }
            }

            if (coveredQty > 0) {
                const avgEntryPrice = totalProceeds / coveredQty;
                // Short PnL: (Entry - Exit) * Qty
                const pnl = (avgEntryPrice - trade.price) * coveredQty;

                completed.push({
                    ticker: ticker,
                    side: 'SHORT',
                    entry_time: firstEntryTime || trade.timestamp,
                    exit_time: trade.timestamp,
                    entry_price: avgEntryPrice,
                    exit_price: trade.price,
                    qty: coveredQty,
                    pnl: pnl
                });
            }
        }
    });

    return completed.reverse(); // Most recent first
}

export function calculateHoldingTime(entryTime, exitTime) {
    const diff = new Date(exitTime) - new Date(entryTime);
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    return `${minutes}m`;
}
