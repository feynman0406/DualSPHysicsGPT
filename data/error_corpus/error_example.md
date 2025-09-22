User: 幫我生成一個2D的波浪模擬 xml file 右邊是斜坡 然後斜坡上要放個石塊在上面 然後模擬波浪打到石頭的交互作用
Xml:<?xml version="1.0" encoding="UTF-8"?>
<case>
  <casedef>
    <constantsdef>
      <gravity x="0" y="0" z="-9.81" units_comment="m/s^2"/>
      <rhop0 value="1000" units_comment="kg/m^3"/>
      <rhopgradient value="3"/>
      <hswl value="0" auto="true"/>
      <gamma value="7"/>
      <speedsystem value="0" auto="true"/>
      <coefsound value="20"/>
      <speedsound value="0" auto="true"/>
      <coefh value="1.3"/>
      <cflnumber value="0.2"/>
    </constantsdef>

    <mkconfig boundcount="240" fluidcount="9">
      <mkorientfluid mk="0" orient="Xyz"/>
    </mkconfig>

    <geometry>
      <definition dp="0.01">
        <pointref x="0" y="0" z="0"/>
        <!-- Thin-Axis Rule: planar 2D -->
        <pointmin x="-7.90" y="0" z="-0.40"/>
        <pointmax x="21.70" y="0" z="1.20"/>
      </definition>

      <commands>
        <mainlist>
          <setshapemode>real | bound</setshapemode>
          <setdrawmode mode="full"/>

          <!-- Left piston (mDBC) -->
          <setmkbound mk="10"/>
          <drawbox>
            <boxfill>solid</boxfill>
            <point x="-0.02" y="-1" z="0.0"/>
            <size  x="0.02"  y="2"  z="0.55"/>
          </drawbox>

          <!-- Tank bottom/right/front/back as fixed DBC -->
          <setdrawmode mode="face"/>
          <setmkbound mk="0"/>
          <drawbox>
            <boxfill>bottom | right | front | back</boxfill>
            <point x="-0.50" y="-1" z="0.0"/>
            <size  x="14.50" y="2"  z="0.55"/>
          </drawbox>

          <!-- Right-hand slope (fixed DBC) -->
          <setdrawmode mode="full"/>
          <setmkbound mk="40"/>
          <drawprism mask="1|2|3|6">
            <!-- y = -1 slice -->
            <point x="8.50" y="-1" z="0.60"/>
            <point x="8.50" y="-1" z="0.00"/>
            <point x="12.00" y="-1" z="0.00"/>
            <point x="14.00" y="-1" z="0.60"/>
            <!-- y = +1 slice -->
            <point x="8.50" y="1" z="0.60"/>
            <point x="8.50" y="1" z="0.00"/>
            <point x="12.00" y="1" z="0.00"/>
            <point x="14.00" y="1" z="0.60"/>
          </drawprism>

          <!-- Rock block on slope (as rigid floating body) -->
          <setmkbound mk="50"/>
          <drawbox>
            <boxfill>solid</boxfill>
            <point x="10.90" y="-0.50" z="0.42"/>
            <size  x="0.30"  y="1.00"  z="0.20"/>
          </drawbox>

          <!-- Fluid region -->
          <setmkfluid mk="0"/>
          <fillbox x="1" y="0" z="0.1">
            <modefill>void</modefill>
            <point x="-0.20" y="-1" z="-0.05"/>
            <size  x="8.70"  y="2"  z="0.50"/>
          </fillbox>

          <shapeout file="" reset="true"/>
        </mainlist>
      </commands>
    </geometry>

    <!-- Enable movement flags (mDBC requires mov="1") -->
    <motion>
      <objreal ref="10">
        <begin mov="1" start="0" finish="100"/>
        <mvnull id="1"/>
      </objreal>
    </motion>

    <!-- Rock behaves as heavy rigid body -->
    <floatings>
      <floating mkbound="50" relativeweight="2.50"/>
    </floatings>
  </casedef>

  <execution>
    <special>
      <wavepaddles>
        <piston>
          <mkbound value="10"/>
          <waveorder value="2"/>
          <start value="0"/>
          <duration value="0.0"/>
          <depth value="0.45"/>
          <pistondir x="1" y="0" z="0"/>
          <waveheight value="0.10"/>
          <waveperiod value="1.20"/>
          <phase value="0"/>
          <ramp value="0"/>
          <savemotion periods="24" periodsteps="20" xpos="4.0" zpos="-0.20"/>
        </piston>
      </wavepaddles>
    </special>

    <parameters>
      <parameter key="SavePosDouble" value="0"/>
      <parameter key="StepAlgorithm" value="2"/>
      <parameter key="VerletSteps" value="40"/>
      <parameter key="Kernel" value="2"/>
      <parameter key="ViscoTreatment" value="1"/>
      <parameter key="Visco" value="0.01" units_comment="m^2/s"/>
      <parameter key="ViscoBoundFactor" value="0"/>
      <parameter key="DensityDT" value="2"/>
      <parameter key="DensityDTvalue" value="0.1"/>
      <parameter key="Shifting" value="0"/>
      <parameter key="ShiftCoef" value="-2"/>
      <parameter key="ShiftTFS" value="1.5"/>
      <parameter key="RigidAlgorithm" value="1"/>
      <parameter key="FtPause" value="0.5" units_comment="s"/>
      <parameter key="CoefDtMin" value="0.05"/>
      <parameter key="DtIni" value="0" units_comment="s"/>
      <parameter key="DtMin" value="0" units_comment="s"/>
      <parameter key="DtFixed" value="0" units_comment="s"/>
      <parameter key="DtFixedFile" value="NONE"/>
      <parameter key="DtAllParticles" value="0"/>
      <parameter key="TimeMax" value="15.0" units_comment="s"/>
      <parameter key="TimeOut" value="0.05" units_comment="s"/>
      <parameter key="PartsOutMax" value="1" units_comment="decimal"/>
      <parameter key="RhopOutMin" value="700" units_comment="kg/m^3"/>
      <parameter key="RhopOutMax" value="1300" units_comment="kg/m^3"/>

      <simulationdomain>
        <posmin x="default" y="default" z="default"/>
        <posmax x="default" y="default" z="default"/>
      </simulationdomain>
    </parameters>
  </execution>
</case>

Feedback:水沒有佈滿整個場域然後石塊放太高了，石塊最底部略微浸入水面下。

fixer_output:
  generator_task:
    target_file: "Case_Def.xml"
    must_output:
      - "single_xml_block"
      - "external_files_list"
      - "checks_block"
    xml_root: "case"
    xml_header: '<?xml version="1.0" encoding="UTF-8"?>'
    apply_edits_from: "required_edits"
    recompute_from: ["computed_values"]
    obey_sections: ["generator_directives","xml_static_checks"]
    precedence:
      - "required_edits"
      - "generator_directives"
      - "xml_static_checks"
      - "previous_xml"
    forbid:
      - "output Case.xml or .bi4 directly"
      - "inventing new tags or schema names"
      - "mixing explanations into XML"
      - "TODO/placeholder text in XML"
    domain_policy:
      reference_aabb: "union(geometry, fluids, moving_trajectories_over_time)"
      min_multiple_per_axis: 2.0
      ensure_centered: true
      required_inset_dp: 2
      forbid_touching_edges: true
      thin_axis_allow_equal: true
      forbid_runtime_expand_beyond_walls: true

  summary: |
    水域僅填到 x≈8.5，未覆蓋斜坡與石塊區；石塊需調整為「底部略低於靜水面」。擴大流體填充至全槽，微調石塊高度，並將 <definition> 依 AABB×2 置中修正。

  root_causes:
    - code: "UserFeedback:WaterNotFull"
      evidence: "水沒有佈滿整個場域"
      cause: "/case/casedef/geometry/commands/mainlist/fillbox 的 x-長度為 8.70（僅到 x=8.5），未覆蓋至右側斜坡與石塊 (x≈10.9)。"
    - code: "UserFeedback:RockTooHigh"
      evidence: "石塊放太高了，石塊最底部略微浸入水面下。"
      cause: "/case/casedef/geometry/commands/mainlist/drawbox（mk=50）之 point z=0.42 與水面 z≈0.45 的關係需調整為微浸沒。"
    - code: "DomainNotCentered"
      evidence: "definition: pointmin.x=-7.90, pointmax.x=21.70（中心 x=6.90），與幾何聯集中心 x≈6.75 不對齊；且尺寸偏大且未依 AABB×2 精準置中。"
      cause: "/case/casedef/geometry/definition 的 pointmin/pointmax 未依『幾何+流體+移動包絡』AABB×2 並置中。"

  required_edits:
    - id: "ED_FLUID_EXTEND_X"
      op: "set"
      path: "/case/casedef/geometry/commands/mainlist/fillbox"
      fields:
        # 讓流體自左端 x=-0.20 填至右牆 x=14.00（與幾何右牆對齊），深度維持至 z=0.45
        "point.x": "-0.20"
        "size.x": "14.20"
        "point.z": "-0.05"
        "size.z": "0.50"
      rationale: "擴充流體至覆蓋全槽（含斜坡與石塊區），確保初始水域完整；保留頂面 z=0.45。"

    - id: "ED_ROCK_ADJUST_Z"
      op: "set"
      path: "/case/casedef/geometry/commands/mainlist/drawbox[mk=50]"
      fields:
        # 使石塊底面略低於靜水面（z=0.45），以 dp=0.01 給 0.005 的微浸沒量
        "point.z": "0.445"
      rationale: "將石塊底部調為略微浸入水面下（約 0.5*dp），滿足用戶意圖且保留與斜坡間足夠間隙。"

    - id: "ED_DOMAIN_RESIZE_CENTER"
      op: "set"
      path: "/case/casedef/geometry/definition"
      fields:
        pointmin.x: "-7.75"
        pointmax.x: "21.25"
        pointmin.z: "-0.385"
        pointmax.z: "0.955"
      rationale: "將 <definition> 調整為『聯集 AABB ×2 並置中』。"

    - id: "ED_DOMAIN_INSET_MARGIN"
      op: "set"
      path: "/case/casedef/geometry/definition"
      fields:
        pointmin.x: "-7.75"
        pointmax.x: "21.25"
        pointmin.z: "-0.385"
        pointmax.z: "0.955"
      rationale: "四周距離遠大於 2*dp，維持 AABB×2 置中且內縮規則成立。"

    - id: "ED_DISABLE_RUNTIME_EXPAND"
      op: "set"
      path: "/case/execution/parameters/simulationdomain/posmax"
      fields: { x: "default", y: "default", z: "default" }
      rationale: "禁止執行期外擴，避免超出槽壁與定義域。"

  computed_values:
    dp: 0.01
    h: 0.02252
    domain_before:
      xmin: -7.90
      xmax: 21.70
      ymin: 0.0
      ymax: 0.0
      zmin: -0.40
      zmax: 1.20
    # 聯集 AABB（採用幾何牆/斜坡/活塞 + 擴充後流體 + 石塊頂部）
    union_aabb:
      xmin: -0.50
      xmax: 14.00
      ymin: 0.0
      ymax: 0.0
      zmin: -0.05
      zmax: 0.62
    union_range:
      dx: 14.50
      dy: 0.0
      dz: 0.67
    domain_after:
      xmin: -7.75
      xmax: 21.25
      ymin: 0.0
      ymax: 0.0
      zmin: -0.385
      zmax: 0.955
    domain_range:
      dx: 29.0
      dy: 0.0
      dz: 1.34
    domain_multiple:
      x: 2.0
      y: null
      z: 2.0
    inset_distance:
      x_minus: 7.25
      x_plus: 7.25
      y_minus: 0.0
      y_plus: 0.0
      z_minus: 0.335
      z_plus: 0.335
    inset_dp_effective_min: 33.5
    centered_error:
      x: 0.0
      y: 0.0
      z: 0.0
    thin_axis: "y"
    moving_mk_set: [10]
    safety_margins:
      inset_dp: 2
      boundary_thickness_min_dp: 1
      wall_fluid_gap_min_dp: 1
      mdbc_fluid_max_gap_h: 2

  generator_directives:
    - "唯一目標輸出：Case_Def.xml（定義檔）。"
    - "XML 嚴用專案範例標籤/層級；禁止自創。"
    - "SI 單位一致（m, kg, s, N）。"
    - "段落順序固定：Parameters → Simulation → Domain → Materials/Fluid → Boundaries → MovingBoundaries → InitialConditions → Waves/Forcing/InletOutlet → Measures/Output → Post/Execution。"
    - "Thin-Axis Rule：以 y=0 定義 2D；不得另設 2D/3D 切換。"
    - "Domain 依『幾何+流體+全時刻移動包絡 AABB』各軸≥2×並居中；四周≥2*dp。"
    - "牆厚≥1*dp；流體與牆間隙≥1*dp。"
    - "mDBC：有法向、<motion> mov=1，行程全在 Domain 內；mDBC—流體距離≲2*h。"
    - "<mkconfig> 唯一且位於 <constantsdef> 之後、<geometry> 之前。"
    - "GenCase v5.4：<hswl auto=\"true\">、<speedsystem auto=\"true\">、<speedsound auto=\"true\"> 必補齊。"
    - "回覆時：先輸出單一 XML 區塊；再列外部檔清單與防呆處置；最後附最小化 checks。"

  xml_static_checks:
    must_have:
      - "/case/casedef/constantsdef"
      - "/case/casedef/mkconfig"
      - "/case/casedef/geometry/definition/pointmin"
      - "/case/casedef/geometry/definition/pointmax"
      - "/case/execution/motion"
    uniqueness:
      - "/case/casedef/mkconfig"
    ordering:
      - "/case/casedef/constantsdef BEFORE /case/casedef/mkconfig"
      - "/case/casedef/mkconfig BEFORE /case/casedef/geometry"
    constraints:
      - "mk indices: 0 ≤ fluid mk < fluidcount；0 ≤ bound mk < boundcount；moving_mk_set ⊆ mk_bound_set"
      - "Domain：聯集 AABB 各軸≥2×且域內縮≥2*dp、並居中"
      - "2D：薄軸相等（y=0）；必要時啟用 periodic 或薄層≤2*dp"
      - "牆厚≥1*dp；牆—流體間隙≥1*dp；mDBC—流體≲2*h；FluidBlock 不被 Domain 切掉"
      - "定義域 min<max（薄軸除外），禁止自創標籤"
      - "Domain 中心與 union AABB 中心對齊（允許 ≤0.5*dp 誤差）"
      - "四周內縮距離 ≥ 2*dp（薄軸除外）"

  smoke_tests:
    gencase_must_pass: ["LoadXMLInit","Draw"]
    solver_must_not_error: ["AbortBoundOut","No normal data for mDBC","Constant 'b' cannot be zero"]
    expected_logs_include: ["Loaded particles","MapRealPos(border)","OmpThreads"]
    min_steps: 2000

  notes:
    - "如需更精準浸沒量，可將石塊底面設為 z=0.45-0.003（0.3*dp）再試。"
    - "若右側區域仍出現空洞，檢查 fillbox 是否被邊界幾何遮擋並確保 <modefill>void</modefill>。"
