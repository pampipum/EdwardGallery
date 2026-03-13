let performanceChart = null;

// Custom plugin to show live value labels on the right side of the chart
const liveValuePlugin = {
    id: 'liveValueLabels',
    afterDraw: (chart) => {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;

        chart.data.datasets.forEach((dataset, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;

            const dataPoints = meta.data;
            if (!dataPoints || dataPoints.length === 0) return;

            const lastPoint = dataPoints[dataPoints.length - 1];
            if (!lastPoint) return;

            const rawData = dataset.data[dataset.data.length - 1];
            const value = rawData?.y ?? rawData;
            if (value === undefined || value === null) return;

            // Glow effect color
            const alphaColor = (color) => {
                if (color.startsWith('#')) return color + '80'; // 50% opacity hex
                return color;
            };

            const isSingle = chart.data.datasets.length === 1;

            // Draw glowing dot ON the final data point
            ctx.save();
            ctx.beginPath();
            ctx.arc(lastPoint.x, lastPoint.y, 5, 0, 2 * Math.PI);
            ctx.fillStyle = dataset.borderColor;
            ctx.shadowColor = dataset.borderColor;
            ctx.shadowBlur = 12;
            ctx.fill();

            // Draw inner white dot for contrast
            ctx.beginPath();
            ctx.arc(lastPoint.x, lastPoint.y, 2.5, 0, 2 * Math.PI);
            ctx.fillStyle = '#ffffff';
            ctx.shadowBlur = 0;
            ctx.fill();
            ctx.restore();

            // Draw pill background
            const text = '$' + value.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });

            ctx.save();
            ctx.font = 'bold 11px "Space Mono", monospace';
            const textWidth = ctx.measureText(text).width;
            const pillWidth = textWidth + 16;
            const pillHeight = 22;

            // Determine Pill position (above point if single, on right edge if multi)
            let pillX, pillY;
            if (isSingle) {
                pillX = lastPoint.x - pillWidth / 2;
                pillY = lastPoint.y - pillHeight - 12;
                // Keep pill inside chart area
                if (pillX < chartArea.left) pillX = chartArea.left;
                if (pillX + pillWidth > chartArea.right) pillX = chartArea.right - pillWidth;
                if (pillY < chartArea.top) pillY = lastPoint.y + 12;
            } else {
                pillX = chartArea.right + 10;
                pillY = lastPoint.y - pillHeight / 2;
            }

            // Draw rounded rectangle background with glow
            ctx.fillStyle = dataset.borderColor;
            ctx.shadowColor = dataset.borderColor;
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.roundRect(pillX, pillY, pillWidth, pillHeight, 11);
            ctx.fill();
            ctx.shadowBlur = 0;

            // Draw text
            ctx.fillStyle = '#0f1012'; // Dark text for contrast against bright pills
            if (dataset.borderColor === '#ef4444' || dataset.borderColor === '#2563eb' || dataset.borderColor === '#dc2626') {
                ctx.fillStyle = '#ffffff'; // White text for darker pills
            }
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, pillX + pillWidth / 2, pillY + pillHeight / 2);
            ctx.restore();
        });
    }
};

// Register the plugin globally
if (typeof Chart !== 'undefined') {
    Chart.register(liveValuePlugin);
}

export function renderChart(historyOrComparisonData, currentValuesOrSingleValue, isComparison = false) {
    const ctx = document.getElementById('performance-chart')?.getContext('2d');
    if (!ctx) return;

    const isMobile = window.innerWidth < 768;
    const rightPadding = isComparison ? (isMobile ? 85 : 120) : (isMobile ? 20 : 40);

    // Safety check: ensure we have valid data
    if (!historyOrComparisonData || (Array.isArray(historyOrComparisonData) && historyOrComparisonData.length === 0)) {
        return;
    }

    let datasets = [];

    if (isComparison) {
        // Comparison Mode - Use time-based x-axis
        const pmColors = {
            'pm1': '#3b82f6', // Blue
            'pm2': '#00e5a0', // Teal/Green
            'pm3': '#ef4444', // Red
            'pm4': '#a855f7', // Purple
            'pm5': '#f97316', // Orange
            'pm6': '#eab308'  // Yellow
        };

        const pmNames = {
            'pm1': 'Adaptive Structural Alpha',
            'pm2': 'The Sentient Structurist',
            'pm3': 'Liquidity Vacuum Alpha',
            'pm4': 'Max Leverage',
            'pm5': 'The Survivor'
        };

        // currentValuesOrSingleValue should be an object with current values for each PM
        const currentValues = currentValuesOrSingleValue || {};

        // Convert each PM's history to time-series data points
        for (const [pmId, history] of Object.entries(historyOrComparisonData)) {
            // Skip PM6 (Shadow Live) from the main comparison chart to preserve scale
            if (pmId === 'pm6') continue;
            
            if (!history || history.length === 0) continue;

            // Create a copy of history to avoid mutating original
            let chartHistory = [...history];

            // Add current value if available and different from last historical value
            const currentValue = currentValues[pmId];
            if (currentValue && history.length > 0) {
                const lastValue = history[history.length - 1].total_value;
                if (Math.abs(currentValue - lastValue) > 0.01) {
                    chartHistory.push({
                        timestamp: new Date().toISOString(),
                        total_value: currentValue
                    });
                }
            }

            // Map to {x: timestamp, y: value} format for time-series
            const dataPoints = chartHistory.map(h => ({
                x: new Date(h.timestamp).getTime(), // Convert to milliseconds
                y: h.total_value
            }));

            datasets.push({
                label: pmNames[pmId] || pmId,
                data: dataPoints,
                borderColor: pmColors[pmId] || '#000000',
                backgroundColor: 'transparent',
                borderWidth: 2.5,
                fill: false,
                tension: 0.35, // Smoother curves
                pointRadius: 0, // Hide points for cleaner lines
                pointHoverRadius: 6,
                pointBackgroundColor: pmColors[pmId] || '#000000',
                spanGaps: false // Don't connect gaps in data
            });
        }
    } else {
        // Single PM Mode
        let chartHistory = [...historyOrComparisonData];
        if (currentValuesOrSingleValue && historyOrComparisonData.length > 0) {
            const lastValue = historyOrComparisonData[historyOrComparisonData.length - 1].total_value;
            if (Math.abs(currentValuesOrSingleValue - lastValue) > 0.01) {
                chartHistory.push({
                    timestamp: new Date().toISOString(),
                    total_value: currentValuesOrSingleValue
                });
            }
        }

        // Map to time-series format
        const dataPoints = chartHistory.map(h => ({
            x: new Date(h.timestamp).getTime(),
            y: h.total_value
        }));

        // Create gradient fill
        const gradientFill = ctx.createLinearGradient(0, 0, 0, 400);
        gradientFill.addColorStop(0, 'rgba(0, 229, 160, 0.25)');
        gradientFill.addColorStop(1, 'rgba(0, 229, 160, 0.02)');

        datasets.push({
            label: 'Portfolio Value',
            data: dataPoints,
            borderColor: '#00e5a0',
            backgroundColor: gradientFill,
            borderWidth: 2.5,
            fill: true,
            tension: 0.35, // Smoother curves
            pointRadius: 0, // Hide points for cleaner lines
            pointHoverRadius: 6,
            pointBackgroundColor: '#00e5a0'
        });
    }

    // Chart configuration
    const config = {
        type: 'line',
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    right: rightPadding // Responsive room for live value pills on right edge
                }
            },
            plugins: {
                legend: {
                    display: isComparison,
                    position: 'top',
                    labels: {
                        color: '#9ca3af',
                        font: {
                            family: "'Space Mono', monospace",
                            size: isMobile ? 9 : 11,
                            weight: 'bold'
                        },
                        padding: isMobile ? 8 : 15,
                        boxWidth: isMobile ? 12 : 20,
                        usePointStyle: true,
                        pointStyle: 'rectRounded'
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(8, 8, 18, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#00e5a0',
                    titleFont: { family: "'Space Mono', monospace", size: 11 },
                    bodyFont: { family: "'Space Mono', monospace", size: 13, weight: 'bold' },
                    borderColor: 'rgba(0, 229, 160, 0.3)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: function (context) {
                            if (context[0]) {
                                const date = new Date(context[0].parsed.x);
                                return date.toLocaleString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                });
                            }
                            return '';
                        },
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += '$' + context.parsed.y.toLocaleString('en-US', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        // unit: 'hour', // Auto-scale
                        displayFormats: {
                            hour: 'HH:mm',
                            day: 'MMM dd'
                        },
                        tooltipFormat: 'MMM dd, HH:mm'
                    },
                    display: true,
                    grid: {
                        display: true,
                        drawBorder: false,
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#6b7280',
                        font: {
                            family: "'Space Mono', monospace",
                            size: isMobile ? 9 : 10
                        },
                        maxTicksLimit: isMobile ? 4 : 8,
                        maxRotation: 0,
                        minRotation: 0,
                        padding: 10
                    }
                },
                y: {
                    display: true,
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: '#4b5563',
                        font: {
                            family: "'Space Mono', monospace",
                            size: 10
                        },
                        callback: function (value) {
                            return '$' + value.toLocaleString('en-US', {
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            });
                        },
                        padding: 15
                    },
                    border: {
                        display: false
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    };

    // Update or create chart
    if (performanceChart) {
        performanceChart.data.datasets = datasets;
        performanceChart.options.plugins.legend.display = isComparison;
        performanceChart.update('none'); // Update without animation for smoother updates
    } else {
        performanceChart = new Chart(ctx, config);
    }
}
