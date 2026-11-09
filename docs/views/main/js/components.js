/**
 * UI Components & Interactive Renderers — Soft Clean Cards
 * Specification: docs/views/main/design-system.md
 * Định hướng: Trình bày chi tiết, ngôn ngữ tự nhiên, phân tích sâu cơ chế kỹ thuật và trade-offs
 */

const UIComponents = {
  // Render Milestone Cards
  renderMilestones: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const milestones = window.PROJECT_DATA.milestonesCompleted;
    container.innerHTML = milestones.map(m => `
      <div class="card" style="justify-content: space-between;">
        <div style="display: flex; flex-direction: column; gap: var(--space-4);">
          <div class="card-header">
            <span class="badge-pill badge-success">
              <span class="dot"></span> ${m.tag}
            </span>
            <span class="text-caption font-mono">${m.id}</span>
          </div>

          <div class="card-title-group">
            <h3 class="text-title-md">${m.title}</h3>
            <p class="text-label" style="line-height: 1.45;">${m.summary}</p>
          </div>

          <div class="card-subtle-box">
            <div class="metric-row">
              <div class="metric-col">
                <span class="metric-label">Tải CPU Pi 3</span>
                <span class="metric-value">${m.metrics.cpuLoad.split(' ')[0]} <span class="metric-unit">Cortex-A53</span></span>
              </div>
              <div class="metric-col">
                <span class="metric-label">Chiếm Bộ Nhớ</span>
                <span class="metric-value">${m.metrics.memory.split(' ')[2]} <span class="metric-unit">MB RAM</span></span>
              </div>
              <div class="metric-col">
                <span class="metric-label">Tốc Độ Khung Hình</span>
                <span class="metric-value" style="color: var(--data-4);">${m.metrics.throughput.split(' ')[2]} <span class="metric-unit">FPS</span></span>
              </div>
            </div>
          </div>
        </div>

        <div>
          <button class="btn-ghost-details" onclick="UIComponents.toggleCollapsible(this)">
            <span>Chi tiết cơ chế & giải pháp đã xử lý</span>
            <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div class="collapsible-content">
            <p style="font-size: 13px; line-height: 1.55; color: var(--text-primary);">${m.details}</p>
          </div>
        </div>
      </div>
    `).join('');
  },

  // Render Officially Approved Architecture Decisions with Deep Engineering Details
  renderApprovedDecisions: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const approved = window.PROJECT_DATA.approvedDecisions;
    container.innerHTML = approved.map(item => `
      <div class="card approved-module-card" style="padding: var(--space-8); border: 1.5px solid rgba(31, 166, 58, 0.35); box-shadow: 0 4px 20px rgba(31, 166, 58, 0.07); display: flex; flex-direction: column; gap: var(--space-5);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-3); border-bottom: 1px solid var(--border-hairline); padding-bottom: var(--space-4);">
          <div style="display: flex; flex-direction: column; gap: var(--space-1);">
            <div style="display: flex; align-items: center; gap: var(--space-3);">
              <span class="badge-pill font-mono" style="background: var(--ink); color: #fff; font-weight: 600;">${item.moduleCode}</span>
              <span class="badge-pill badge-success"><span class="dot"></span> ĐÃ PHÊ DUYỆT CHÍNH THỨC</span>
            </div>
            <h3 class="text-title-lg" style="margin-top: 6px; font-size: 20px;">${item.moduleName}</h3>
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 2px;">
              <span class="text-caption" style="font-weight: 600; color: var(--text-secondary); text-transform: uppercase; font-size: 11.5px;">Phương án đã chốt:</span>
              <span style="color: var(--data-4); font-weight: 600; font-size: 15px;">${item.chosenTech}</span>
            </div>
          </div>
          <div class="badge-pill" style="font-size: 12px; padding: 6px 12px; background: #ffffff; border: 1px solid var(--border-card);">
            Cột mốc: Release 2 Pipeline
          </div>
        </div>

        <!-- Strategic Summary -->
        <p class="text-body" style="font-size: 14.5px; line-height: 1.55; color: var(--text-primary);">
          ${item.summary}
        </p>

        <!-- Metric Row -->
        <div class="card-subtle-box" style="padding: var(--space-4);">
          <div class="metric-row">
            <div class="metric-col">
              <span class="metric-label">Độ Trễ / Tốc Độ</span>
              <span class="metric-value" style="color: var(--data-4);">${item.metrics.latency || item.metrics.publishRate}</span>
            </div>
            <div class="metric-col">
              <span class="metric-label">Tài Nguyên / Nền Tảng</span>
              <span class="metric-value">${item.metrics.compute || item.metrics.accuracyClose || item.metrics.compatibility}</span>
            </div>
            <div class="metric-col">
              <span class="metric-label">Độ Chính Xác / Tin Cậy</span>
              <span class="metric-value">${item.metrics.accuracy || item.metrics.accuracyFar || item.metrics.blindspotFix || item.metrics.lidarReady}</span>
            </div>
          </div>
        </div>

        <!-- Toggle Button for Deep-Dive Details -->
        <div>
          <button class="btn-ghost-details" onclick="UIComponents.toggleCollapsible(this)">
            <span>Xem tài liệu kỹ thuật chuyên sâu & hướng dẫn triển khai chi tiết</span>
            <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          
          <div class="collapsible-content">
            <div style="display: flex; flex-direction: column; gap: var(--space-5); padding-top: var(--space-4);">
              <!-- 1. Physics & Math Derivation -->
              <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: var(--space-4); border-left: 3px solid var(--data-1);">
                <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 4px;">
                  1. Bản chất vật lý & Thách thức cần khắc phục:
                </span>
                <p style="font-size: 13.5px; line-height: 1.55; color: var(--text-primary);">
                  ${item.deepDive.problemContext}
                </p>
                ${item.deepDive.mathDerivation ? `
                  <div style="margin-top: var(--space-3); padding-top: var(--space-2); border-top: 1px solid var(--border-hairline);">
                    <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 4px;">
                      Mô hình toán học & Công thức giải tích:
                    </span>
                    <p style="font-size: 13.5px; line-height: 1.55; color: var(--text-primary);">
                      ${item.deepDive.mathDerivation}
                    </p>
                  </div>
                ` : ''}
              </div>

              <!-- 2. Detailed Mechanism & Edge AI Optimization -->
              <div style="background: #ffffff; border: 1px solid var(--border-hairline); border-radius: var(--radius-md); padding: var(--space-5);">
                <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 6px;">
                  2. Cơ chế hoạt động cụ thể & Tối ưu hóa Edge AI:
                </span>
                <p style="font-size: 13.5px; line-height: 1.6; color: var(--text-primary);">
                  ${item.deepDive.mechanism || item.deepDive.hardwareProtocol}
                </p>
              </div>

              <!-- 3. Implementation Guide -->
              ${item.deepDive.stepByStepGuide ? `
                <div style="background: #ffffff; border: 1px solid var(--border-hairline); border-radius: var(--radius-md); padding: var(--space-5);">
                  <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 6px;">
                    3. Hướng dẫn triển khai từng bước:
                  </span>
                  <ul style="list-style: none; display: flex; flex-direction: column; gap: var(--space-2); padding-left: 0;">
                    ${item.deepDive.stepByStepGuide.map(step => `
                      <li style="font-size: 13px; line-height: 1.5; color: var(--text-primary);">
                        ${step}
                      </li>
                    `).join('')}
                  </ul>
                </div>
              ` : ''}

              <!-- 4. Edge Cases & Fault Tolerance -->
              ${item.deepDive.edgeCases ? `
                <div style="background: rgba(184, 80, 0, 0.05); border: 1px solid rgba(184, 80, 0, 0.2); border-radius: var(--radius-md); padding: var(--space-4);">
                  <span class="text-label" style="font-weight: 600; color: #b85000; text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 4px;">
                    4. Xử lý tình huống biên & Cơ chế phòng vệ:
                  </span>
                  <p style="font-size: 13.5px; line-height: 1.55; color: var(--text-primary);">
                    ${item.deepDive.edgeCases}
                  </p>
                </div>
              ` : ''}

              <!-- 5. Benchmark Protocol -->
              ${item.deepDive.benchmarkProtocol ? `
                <div style="background: rgba(31, 166, 58, 0.05); border: 1px solid rgba(31, 166, 58, 0.2); border-radius: var(--radius-md); padding: var(--space-4);">
                  <span class="text-label" style="font-weight: 600; color: var(--data-4); text-transform: uppercase; font-size: 12px; display: block; margin-bottom: 4px;">
                    5. Giao thức nghiệm thu định lượng:
                  </span>
                  <p style="font-size: 13.5px; line-height: 1.55; color: var(--text-primary);">
                    ${item.deepDive.benchmarkProtocol}
                  </p>
                </div>
              ` : ''}

              <!-- 6. Implementation Checklist -->
              <div style="border-top: 1px solid var(--border-hairline); padding-top: var(--space-3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3);">
                  <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px;">
                    Checklist kỹ thuật & nghiệm thu:
                  </span>
                  ${item.deepDive.visualizerLink ? `
                    <a href="${item.deepDive.visualizerLink}" class="badge-pill badge-active" style="text-decoration: none; font-size: 11px;" target="_blank">
                      ${item.deepDive.visualizerLabel} ↗
                    </a>
                  ` : ''}
                </div>
                <ul style="list-style: none; display: flex; flex-direction: column; gap: var(--space-2); padding-left: 0;">
                  ${item.deepDive.checklist.map(chk => `
                    <li style="display: flex; align-items: flex-start; gap: var(--space-2); font-size: 13px; line-height: 1.45; color: var(--text-secondary);">
                      <span style="color: var(--data-4); font-weight: 700; flex-shrink: 0;">✔</span>
                      <span>${chk}</span>
                    </li>
                  `).join('')}
                </ul>
              </div>

            </div>
          </div>
        </div>
      </div>
    `).join('');
  },

  // Render Proposed Solution Modules with Rich Natural Language
  renderSolutions: function(containerId, filterCategory = "all") {
    const container = document.getElementById(containerId);
    if (!container) return;

    const modules = window.PROJECT_DATA.proposedModules;
    let html = "";

    modules.forEach(mod => {
      if (filterCategory !== "all" && mod.category !== filterCategory) return;

      html += `
        <div class="card" style="margin-bottom: var(--space-8); padding: var(--space-8); gap: var(--space-6);" data-category="${mod.category}">
          <!-- Module Header & Problem Statement -->
          <div style="border-bottom: 1px solid var(--border-hairline); padding-bottom: var(--space-5); display: flex; flex-direction: column; gap: var(--space-3);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-2);">
              <div style="display: flex; align-items: center; gap: var(--space-3);">
                <span class="badge-pill font-mono" style="background: var(--ink); color: #fff; font-weight: 600;">${mod.code}</span>
                <h3 class="text-title-lg" style="font-size: 20px;">${mod.name}</h3>
              </div>
              <span class="badge-pill badge-warning">
                <span class="dot"></span> ${mod.stage}
              </span>
            </div>

            <!-- Problem Explanation in Natural Language -->
            <div style="background: var(--bg-subtle); border-radius: var(--radius-lg); padding: var(--space-5); border-left: 3px solid var(--data-1); display: flex; flex-direction: column; gap: var(--space-2);">
              <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-2);">
                <span class="text-label" style="font-weight: 600; color: var(--text-primary); text-transform: uppercase; font-size: 12px; letter-spacing: 0.03em;">
                  Bản chất bài toán & Thách thức kỹ thuật thực tế
                </span>
                ${mod.visualizerLink ? `
                  <a href="${mod.visualizerLink}" class="badge-pill badge-active" style="text-decoration: none; font-size: 11px;" target="_blank">
                    ${mod.visualizerLabel} ↗
                  </a>
                ` : ''}
              </div>
              <p class="text-body" style="line-height: 1.55; color: var(--text-primary); font-size: 14px;">
                ${mod.problemStatement}
              </p>
            </div>
          </div>

          <!-- Candidate Solutions Cards Grid -->
          <div style="display: flex; flex-direction: column; gap: var(--space-2);">
            <span class="text-label" style="font-weight: 600; color: var(--text-secondary); text-transform: uppercase; font-size: 12px;">
              Các giải pháp dự kiến đang cân nhắc:
            </span>
            <div class="solutions-grid" style="margin-top: var(--space-2);">
              ${mod.solutions.map(sol => {
                const isRec = sol.type === "recommended";
                const badgeType = isRec ? "badge-success" : (sol.type === "baseline" ? "badge-active" : "badge-warning");

                return `
                  <div class="solution-card" style="${isRec ? 'border: 1.5px solid rgba(31, 166, 58, 0.35); box-shadow: 0 4px 18px rgba(31, 166, 58, 0.08);' : ''}">
                    <div class="card-header">
                      <div class="solution-badges">
                        <span class="badge-pill ${badgeType}">
                          <span class="dot"></span> ${sol.tag}
                        </span>
                      </div>
                      <span class="font-mono text-caption" style="color: var(--text-tertiary);">${sol.id}</span>
                    </div>

                    <div class="card-title-group">
                      <h4 class="text-title-md" style="font-size: 17px;">${sol.name}</h4>
                    </div>

                    <!-- Metrics -->
                    <div class="metric-row card-subtle-box" style="padding: 12px 14px;">
                      <div class="metric-col">
                        <span class="metric-label">Độ Trễ Dự Kiến</span>
                        <span class="metric-value" style="color: ${isRec ? 'var(--data-4)' : 'var(--text-primary)'};">${sol.latency}</span>
                      </div>
                      <div class="metric-col">
                        <span class="metric-label">Tài Nguyên</span>
                        <span class="metric-value" style="font-size: 13px;">${sol.compute.split('/')[0]}</span>
                      </div>
                      <div class="metric-col">
                        <span class="metric-label">Độ Chính Xác</span>
                        <span class="metric-value" style="font-size: 13px;">${sol.accuracy.split('·')[0]}</span>
                      </div>
                    </div>

                    <!-- Detailed Description in Natural Language -->
                    <div style="font-size: 13.5px; line-height: 1.55; color: var(--text-primary); background: #ffffff; border: 1px solid var(--border-hairline); border-radius: var(--radius-md); padding: 12px 14px;">
                      <strong style="color: var(--text-primary); display: block; margin-bottom: 4px; font-size: 12.5px; text-transform: uppercase; letter-spacing: 0.02em;">Cơ chế hoạt động cụ thể:</strong>
                      ${sol.description}
                    </div>

                    <!-- Trade-offs -->
                    <div class="tradeoff-list" style="margin-top: 4px;">
                      <div class="text-label" style="font-weight: 600; color: var(--text-primary); font-size: 12px;">Ưu điểm vượt trội:</div>
                      ${sol.pros.map(pro => `
                        <div class="tradeoff-item">
                          <span class="icon tradeoff-pro">✓</span>
                          <span class="text-caption" style="color: var(--text-primary); font-size: 12.5px; line-height: 1.45;">${pro}</span>
                        </div>
                      `).join('')}

                      <div class="text-label" style="font-weight: 600; color: var(--text-primary); font-size: 12px; margin-top: 6px;">Hạn chế & Điểm cần lưu ý:</div>
                      ${sol.cons.map(con => `
                        <div class="tradeoff-item">
                          <span class="icon tradeoff-con">!</span>
                          <span class="text-caption" style="color: var(--text-secondary); font-size: 12.5px; line-height: 1.45;">${con}</span>
                        </div>
                      `).join('')}
                    </div>

                    <!-- Actionable Takeaway / Lab Recommendation -->
                    <div style="margin-top: auto; padding-top: var(--space-4); border-top: 1px solid var(--border-hairline);">
                      <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: 10px 12px; font-size: 12px; line-height: 1.45; color: var(--text-secondary);">
                        <strong style="color: var(--text-primary);">Định hướng tại Lab:</strong> ${sol.recommendationReason}
                      </div>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  // Render Decision Matrix Table
  renderDecisionMatrix: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const matrix = window.PROJECT_DATA.decisionMatrix;
    let html = `
      <div class="clean-table-container">
        <table class="clean-table">
          <thead>
            <tr>
              <th style="min-width: 170px;">Cụm Module</th>
              <th style="min-width: 250px;">Phương Án Kỹ Thuật</th>
              <th>Độ Trễ (Jetson)</th>
              <th>Chiếm VRAM</th>
              <th>Độ Chính Xác</th>
              <th>Tính Khả Thi</th>
              <th style="min-width: 260px;">Nhận Định Kỹ Thuật & Khuyến Nghị</th>
            </tr>
          </thead>
          <tbody>
    `;

    matrix.forEach(group => {
      group.candidates.forEach((cand, idx) => {
        const isRec = cand.recommend;
        html += `
          <tr style="${isRec ? 'background: rgba(31, 166, 58, 0.04); font-weight: 500;' : ''}">
            ${idx === 0 ? `<td rowspan="${group.candidates.length}" style="font-weight: 600; vertical-align: top; border-right: 1px solid var(--border-hairline); background: var(--bg-subtle);">${group.module}</td>` : ''}
            <td>
              <div style="display: flex; align-items: center; gap: 8px;">
                ${isRec ? '<span style="color: var(--data-4); font-size: 14px;">★</span>' : ''}
                <span>${cand.name}</span>
              </div>
            </td>
            <td class="font-mono">${cand.latency}</td>
            <td class="font-mono">${cand.vram}</td>
            <td>${cand.absRel}</td>
            <td><span class="badge-pill" style="font-size: 11px;">${cand.ready}</span></td>
            <td>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <span style="font-size: 12px; color: ${isRec ? 'var(--text-primary)' : 'var(--text-secondary)'}; line-height: 1.35;">${cand.note}</span>
                ${isRec 
                  ? '<span class="badge-pill badge-success" style="width: fit-content; font-size: 10.5px;"><span class="dot"></span> ĐÃ CHỐT CHÍNH THỨC</span>' 
                  : '<span class="badge-pill" style="width: fit-content; font-size: 10.5px; color: var(--text-tertiary);"><span class="dot" style="background: var(--text-tertiary);"></span> Dự phòng / So sánh</span>'}
              </div>
            </td>
          </tr>
        `;
      });
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = html;
  },

  // Render Decision Gates Timeline
  renderDecisionGates: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const gates = window.PROJECT_DATA.decisionGates;
    container.innerHTML = gates.map(gate => `
      <div class="gate-card ${gate.status}">
        <div class="gate-header">
          <span class="gate-id">${gate.id}</span>
          <span class="badge-pill ${gate.badgeClass}">
            <span class="dot"></span> ${gate.statusLabel}
          </span>
        </div>
        <h4 class="gate-title">${gate.title}</h4>
        <p class="gate-desc"><strong>Tiêu chuẩn:</strong> ${gate.criteria}</p>
        <div style="background: var(--bg-subtle); border-radius: var(--radius-xs); padding: 8px 10px; font-size: 11.5px; color: var(--text-primary); line-height: 1.4;">
          ${gate.result}
        </div>
      </div>
    `).join('');
  },

  // Render Recommended Architecture
  renderRecommendedPipeline: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const arch = window.PROJECT_DATA.recommendedArchitecture;
    container.innerHTML = `
      <div class="recommendation-card">
        <div class="card-header" style="border-bottom: 1px solid var(--border-hairline); padding-bottom: var(--space-4);">
          <div class="card-title-group">
            <span class="badge-pill badge-success"><span class="dot"></span> Đề Xuất Chiến Lược Thống Nhất</span>
            <h3 class="text-title-lg" style="margin-top: 4px;">${arch.title}</h3>
            <p class="text-label" style="font-size: 14.5px; max-width: 860px; line-height: 1.5;">${arch.summary}</p>
          </div>
        </div>

        <div class="recommendation-pipeline">
          ${arch.steps.map(s => `
            <div class="pipeline-step">
              <span class="pipeline-step-badge">${s.step}</span>
              <div class="pipeline-step-title">${s.title}</div>
              <div class="pipeline-step-tech">${s.tech}</div>
              <p class="text-caption" style="color: var(--text-secondary); margin-top: 4px; line-height: 1.35;">${s.note}</p>
            </div>
          `).join('')}
        </div>

        <div style="background: #ffffff; border-radius: var(--radius-lg); padding: var(--space-5); border: 1px solid var(--border-card); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-4);">
          <div>
            <div class="text-title-md" style="font-size: 15px;">Tổng ngân sách dự tính toàn trình sau khi chốt</div>
            <p class="text-label">Tốc độ ~22 - 25 FPS · Độ trễ < 45 ms · VRAM chiếm dụng ~1.5 GB trên Jetson AGX Xavier · Sẵn sàng ROS 2</p>
          </div>
          <a href="#decision-matrix" class="btn-primary" style="padding: 9px 20px; font-size: 13px;">
            Xem ma trận so sánh chi tiết
          </a>
        </div>
      </div>
    `;
  },

  // Render Documentation Links
  renderDocumentationLinks: function(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const links = window.PROJECT_DATA.documentationLinks;
    container.innerHTML = links.map(doc => `
      <a href="../../../${doc.path}" class="doc-link-item" target="_blank">
        <div style="display: flex; flex-direction: column; gap: 3px;">
          <span style="color: var(--text-primary); font-weight: 600; font-size: 13.5px;">${doc.title}</span>
          <span class="text-caption" style="color: var(--text-secondary); line-height: 1.4;">${doc.desc}</span>
          <span class="font-mono text-caption" style="color: var(--data-1); font-size: 11px; margin-top: 2px;">${doc.path}</span>
        </div>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0; color: var(--text-tertiary); margin-left: 8px;">
          <line x1="7" y1="17" x2="17" y2="7"></line>
          <polyline points="7 7 17 7 17 17"></polyline>
        </svg>
      </a>
    `).join('');
  },

  // Toggle collapsible block
  toggleCollapsible: function(btn) {
    btn.classList.toggle("expanded");
    const content = btn.nextElementSibling;
    if (content) {
      content.classList.toggle("open");
    }
  }
};

window.UIComponents = UIComponents;
