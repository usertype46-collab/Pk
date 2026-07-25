import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = "https://cnkxsxhgdtuxknrzufhv.supabase.co";
const SUPABASE_KEY = "sb_publishable_QEoX_f9G_Gf9kaaDZpaH-g_ageY5WFK";
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export default function SimulatorEditor() {
    const svgRef = useRef(null);
    const workerRef = useRef(null);
    const [pathD, setPathD] = useState('');
    const [pathCoords, setPathCoords] = useState([]);
    const [cards, setCards] = useState({});
    const [progressMap, setProgressMap] = useState({});
    
    // 卡片客製化設定狀態
    const [cardStyle, setCardStyle] = useState({ minWidth: 50, height: 26, fontSize: 12 });

    // 1. 初始化資料庫與 Web Worker
    useEffect(() => {
        const fetchSettings = async () => {
            const { data } = await supabase.from('powder_settings').select('*');
            const pathData = data.find(d => d.key === 'track_path_d');
            if (pathData) {
                setPathD(pathData.value);
                setPathCoords(parsePathToCoords(pathData.value));
            }
        };
        fetchSettings();

        // 啟動 Worker
        workerRef.current = new Worker('/simulationWorker.js');
        workerRef.current.onmessage = (e) => {
            if (e.data.type === 'PROGRESS_UPDATE') {
                setProgressMap(e.data.payload);
            } else if (e.data.type === 'AUTO_UNLOAD') {
                handleAutoUnload(e.data.cardId);
            }
        };

        // 訂閱 Supabase 實時資料
        const channel = supabase.channel('schema-db-changes')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'powder_cards' }, payload => {
                fetchCards(); // 觸發重取資料
            }).subscribe();

        fetchCards();
        return () => {
            workerRef.current.postMessage({ type: 'STOP' });
            supabase.removeChannel(channel);
        };
    }, []);

    const fetchCards = async () => {
        const { data } = await supabase.from('powder_cards').select('*');
        const cardsObj = data.reduce((acc, card) => ({ ...acc, [card.id]: card }), {});
        setCards(cardsObj);
        workerRef.current.postMessage({ type: 'SYNC_STATE', payload: { cards: cardsObj, line_speed: 1100 } });
    };

    const handleAutoUnload = async (cardId) => {
        await supabase.from('powder_cards').update({ status: 'unloading' }).eq('id', cardId);
    };

    // 2. D3.js SVG 拖拉節點邏輯
    useEffect(() => {
        if (!svgRef.current || pathCoords.length === 0) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll(".node-handle").remove();

        // 建立拖拉行為
        const drag = d3.drag()
            .on("start", function() { d3.select(this).raise().attr("stroke", "#e74c3c"); })
            .on("drag", function(event, d) {
                // 限制在畫布範圍內
                d.x = Math.max(0, Math.min(1000, event.x));
                d.y = Math.max(0, Math.min(1333, event.y));
                
                d3.select(this).attr("cx", d.x).attr("cy", d.y);
                
                // 即時更新路線 Path
                const newD = coordsToPathD(pathCoords);
                setPathD(newD);
                svg.select("#trackPath").attr("d", newD);
            })
            .on("end", async function() {
                d3.select(this).attr("stroke", "#fff");
                // 拖拉結束，回傳 Supabase
                const finalD = coordsToPathD(pathCoords);
                await supabase.from('powder_settings').upsert({ key: 'track_path_d', value: finalD });
            });

        // 繪製控制節點
        svg.selectAll(".node-handle")
            .data(pathCoords)
            .enter()
            .append("circle")
            .attr("class", "node-handle")
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", 12)
            .attr("fill", "#f1c40f")
            .attr("stroke", "#fff")
            .attr("stroke-width", 2)
            .style("cursor", "grab")
            .call(drag);

    }, [pathCoords]);

    // 解析 Path 座標輔助函數[span_8](start_span)[span_8](end_span)
    const parsePathToCoords = (dStr) => {
        const coords = [];
        const regex = /[ML]\s*([0-9.]+)\s+([0-9.]+)/g;
        let match;
        while ((match = regex.exec(dStr)) !== null) {
            coords.push({ x: parseFloat(match[1]), y: parseFloat(match[2]) });
        }
        return coords;
    };
    
    const coordsToPathD = (coords) => {
        if (coords.length === 0) return '';
        let d = `M ${coords[0].x} ${coords[0].y} `;
        for (let i = 1; i < coords.length; i++) {
            d += `L ${coords[i].x} ${coords[i].y} `;
        }
        return d + 'Z';
    };

    // 3. 渲染畫面上的流動物料
    const renderAnimatedCards = () => {
        const trackEl = document.getElementById('trackPath');
        if (!trackEl) return null;
        const trackLength = trackEl.getTotalLength();

        return Object.values(cards).filter(c => c.status === 'on_line').map(card => {
            const progress = progressMap[card.id] || 0;
            const point = trackEl.getPointAtLength(progress * trackLength);
            
            return (
                <div key={card.id} style={{
                    position: 'absolute',
                    left: `${(point.x / 1000) * 100}%`,
                    top: `${(point.y / 1333) * 100}%`,
                    minWidth: `${cardStyle.minWidth}px`,
                    height: `${cardStyle.height}px`,
                    fontSize: `${cardStyle.fontSize}px`,
                    backgroundColor: card.color_code || '#333',
                    transform: 'translate(-50%, -50%)',
                    borderRadius: '4px', border: '2px solid #fff',
                    color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 2px 5px rgba(0,0,0,0.5)', zIndex: 10, cursor: 'pointer'
                }}>
                    {card.part_name || card.part_no}
                </div>
            );
        });
    };

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px' }}>
            <div style={{ flex: 1, maxWidth: '400px' }}>
                <h3>⚙️ 軌道與卡片客製化設定</h3>
                <div style={{ background: 'white', padding: '15px', borderRadius: '8px', boxShadow: '0 2px 5px rgba(0,0,0,0.1)' }}>
                    <label>卡片最小寬度 (px):</label>
                    <input type="number" value={cardStyle.minWidth} onChange={e => setCardStyle({...cardStyle, minWidth: e.target.value})} style={inputStyle} />
                    <label>卡片高度 (px):</label>
                    <input type="number" value={cardStyle.height} onChange={e => setCardStyle({...cardStyle, height: e.target.value})} style={inputStyle} />
                    <label>卡片字體大小 (px):</label>
                    <input type="number" value={cardStyle.fontSize} onChange={e => setCardStyle({...cardStyle, fontSize: e.target.value})} style={inputStyle} />
                    
                    <p style={{ fontSize: '12px', color: '#666', marginTop: '15px' }}>
                        🎯 互動式節點微調：請在右側圖紙中，直接拖曳黃色圓點改變軌道走向。
                    </p>
                </div>
            </div>

            <div style={{ 
                flex: 2, position: 'relative', maxWidth: '768px', aspectRatio: '768/1024',
                backgroundImage: 'url(/14436_2.png)', backgroundSize: 'cover', 
                borderRadius: '10px', overflow: 'hidden', border: '2px solid #ccc'
            }}>
                <svg ref={svgRef} viewBox="0 0 1000 1333" style={{ position: 'absolute', width: '100%', height: '100%', top: 0, left: 0 }}>
                    <path id="trackPath" d={pathD} fill="none" stroke="#e74c3c" strokeWidth="8" strokeDasharray="10, 8" />
                </svg>
                {renderAnimatedCards()}
            </div>
        </div>
    );
}

const inputStyle = { width: '100%', padding: '8px', marginBottom: '10px', boxSizing: 'border-box' };
