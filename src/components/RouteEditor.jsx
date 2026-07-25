import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { supabase } from '../supabase';

const RouteEditor = ({ pageName, title }) => {
    const svgRef = useRef();
    const [pathD, setPathD] = useState('');
    const [cardStyle, setCardStyle] = useState({ width: 50, height: 26, font_size: 12 });
    
    // 解析原始 M x y L x y Z 字串的 Regex[span_9](start_span)[span_9](end_span)
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

    useEffect(() => {
        const loadSettings = async () => {
            const { data: pathData } = await supabase.from('powder_settings').select('value').eq('key', 'track_path_d').single();
            if (pathData) setPathD(pathData.value);

            const { data: styleData } = await supabase.from('card_styles').select('*').eq('page_name', pageName).single();
            if (styleData) setCardStyle(styleData);
        };
        loadSettings();
    }, [pageName]);

    useEffect(() => {
        if (!pathD) return;
        
        let coords = parsePathToCoords(pathD);
        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove();

        // 繪製動態虛線軌道
        const path = svg.append("path")
            .attr("d", pathD)
            .attr("fill", "none")
            .attr("stroke", "#e74c3c")
            .attr("stroke-width", 6)
            .attr("stroke-dasharray", "10, 8")
            .attr("class", "animated-track");

        // 定義 D3 拖拉事件
        const drag = d3.drag()
            .on("start", function() {
                d3.select(this).attr("stroke", "white").attr("stroke-width", 3);
            })
            .on("drag", function(event, d) {
                // 限制座標在視圖範圍內
                d.x = Math.max(0, Math.min(1000, event.x));
                d.y = Math.max(0, Math.min(1333, event.y));
                
                d3.select(this).attr("cx", d.x).attr("cy", d.y);
                const newD = coordsToPathD(coords);
                path.attr("d", newD); // 即時更新線條
            })
            .on("end", async function() {
                d3.select(this).attr("stroke", "none");
                const newD = coordsToPathD(coords);
                setPathD(newD);
                // 儲存至資料庫
                await supabase.from('powder_settings').upsert({ key: 'track_path_d', value: newD });
            });

        // 繪製可拖拉的節點
        svg.selectAll("circle.node")
            .data(coords)
            .enter()
            .append("circle")
            .attr("class", "node")
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", 12)
            .attr("fill", "#f1c40f")
            .style("cursor", "grab")
            .call(drag);

        // 加入簡單的 CSS 動畫讓軌道流動
        svg.append("style").text(`
            .animated-track { animation: moveChain 1.5s linear infinite; }
            @keyframes moveChain { from { stroke-dashoffset: 18; } to { stroke-dashoffset: 0; } }
            circle.node:active { cursor: grabbing !important; fill: #e67e22; }
        `);

    }, [pathD]);

    const handleStyleChange = async (field, value) => {
        const newStyle = { ...cardStyle, [field]: Number(value) };
        setCardStyle(newStyle);
        await supabase.from('card_styles').update({ [field]: Number(value) }).eq('page_name', pageName);
    };

    return (
        <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
            <h2>{title} - 參數設定與視角</h2>
            
            <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                <h4 style={{ margin: '0 0 10px 0' }}>卡片尺寸客製化</h4>
                <div style={{ display: 'flex', gap: '15px' }}>
                    <label>寬度 (px): <input type="number" value={cardStyle.width} onChange={e => handleStyleChange('width', e.target.value)} /></label>
                    <label>高度 (px): <input type="number" value={cardStyle.height} onChange={e => handleStyleChange('height', e.target.value)} /></label>
                    <label>字體大小 (px): <input type="number" value={cardStyle.font_size} onChange={e => handleStyleChange('font_size', e.target.value)} /></label>
                </div>
            </div>

            <div style={{ 
                position: 'relative', 
                width: '100%', 
                maxWidth: '768px',
                aspectRatio: '768 / 1024',
                backgroundImage: 'url(/14436_2.png)',
                backgroundSize: 'cover',
                border: '3px solid #2c3e50',
                borderRadius: '10px',
                overflow: 'hidden'
            }}>
                <svg ref={svgRef} viewBox="0 0 1000 1333" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}></svg>
                
                {/* 預覽卡片 */}
                <div style={{
                    position: 'absolute', top: '20px', left: '20px',
                    width: `${cardStyle.width}px`, height: `${cardStyle.height}px`,
                    fontSize: `${cardStyle.font_size}px`,
                    background: '#34495e', color: 'white', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', borderRadius: '4px',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.3)', border: '2px solid white'
                }}>
                    範例卡片
                </div>
            </div>
        </div>
    );
};

export default RouteEditor;
