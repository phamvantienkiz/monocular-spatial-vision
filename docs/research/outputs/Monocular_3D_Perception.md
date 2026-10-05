# Nghiên Cứu Chuyên Sâu Về Nhận Thức Không Gian 3D Từ Camera RGB Đơn Kính (Monocular 3D Perception)

## 1\. Bản Chất Bài Toán Monocular 3D Perception

Nhận thức không gian 3D từ một camera RGB đơn kính (monocular 3D perception) đóng vai trò nền tảng trong thị giác máy tính, xe tự hành và robot học. Bản chất cốt lõi của bài toán này là việc khôi phục lại cấu trúc không gian ba chiều từ một ma trận điểm ảnh hai chiều, một quá trình vốn dĩ không thể đảo ngược (non-invertible) do sự mất mát thông tin về chiều sâu trong quá trình chiếu phối cảnh.

Một camera RGB đơn lẻ hoạt động như một cảm biến thu nhận cường độ ánh sáng và màu sắc dọc theo các tia sáng hội tụ về quang tâm. Từ một bức ảnh duy nhất, hệ thống có thể trích xuất các thông tin ngữ nghĩa mạnh mẽ như loại đối tượng, kết cấu bề mặt, và các điểm đặc trưng hình học. Về mặt không gian, hệ thống có thể suy ra chính xác vector hướng (ray direction) từ quang tâm đến bất kỳ điểm ảnh nào, tạo cơ sở cho việc xác định góc nhìn ngang (azimuth) và góc nhìn dọc (elevation) của vật thể. Khả năng phân tích kết cấu và bóng đổ cũng cho phép suy đoán tương đối về hình dáng bề mặt (surface normals) và cấu trúc tô-pô của đối tượng.

Tuy nhiên, những thông tin liên quan đến khoảng cách tuyệt đối (metric depth) và kích thước vật lý của đối tượng hoàn toàn không thể xác định nếu không có thêm thông tin tiên nghiệm (prior). Mọi điểm nằm trên cùng một tia chiếu trong không gian 3D đều hội tụ về một pixel duy nhất trên mặt phẳng ảnh, dẫn đến việc khoảng cách dọc theo tia chiếu bị triệt tiêu hoàn toàn. Sự thiếu vắng thông tin chiều sâu kéo theo việc hệ thống không thể phân biệt giữa một vật thể nhỏ ở cự ly gần và một vật thể khổng lồ có hình dáng tương tự ở cự ly xa.

Giới hạn lý thuyết lớn nhất của thị giác đơn kính được định nghĩa là sự mơ hồ về tỷ lệ (scale ambiguity). Trong không gian toán học, nếu một cấu trúc 3D $\mathbf{P}_W$ và một quỹ đạo camera giải thích hoàn hảo một tập hợp các quan sát trên ảnh 2D, thì mọi cấu trúc $\mathbf{P}'_W = s \mathbf{P}_W$ được nhân với một hệ số tỷ lệ $s > 0$ bất kỳ cũng sẽ tạo ra hình chiếu 2D hoàn toàn y hệt. Sự mơ hồ về quy mô này chứng minh rằng, ở cấp độ hình học thuần túy, monocular vision chỉ có thể phục hồi không gian lên đến một hệ số vô hướng (up-to-scale). Để phá vỡ giới hạn này và đạt được đo lường chuẩn xác (metric scale), hệ thống bắt buộc phải tích hợp các nguồn tri thức bên ngoài như mô hình vật lý của đối tượng, chiều cao lắp đặt camera, dữ liệu cảm biến quán tính (IMU), hoặc các tri thức quy mô lớn được học thông qua mạng nơ-ron nhân tạo.

## 2\. Camera Geometry và Calibration

Việc xây dựng một ánh xạ toán học chính xác giữa không gian thế giới thực và mặt phẳng điểm ảnh là bước đầu tiên để hiện thực hóa mọi thuật toán đo đạc 3D.

Mô hình camera lỗ kim (Pinhole camera model) là nền tảng hình học biểu diễn quá trình ánh xạ này. Khởi đầu, một điểm 3D $\mathbf{P}_W = [X_W, Y_W, Z_W]^T$ trong hệ tọa độ thế giới được chuyển đổi sang hệ tọa độ camera thông qua ma trận ngoại hàm (extrinsic parameters). Ma trận ngoại hàm bao gồm một ma trận xoay $\mathbf{R}$ kích thước $3 \times 3$ và một vector tịnh tiến $\mathbf{t}$ kích thước $3 \times 1$, đại diện cho tư thế 6 bậc tự do (6D pose) của camera trong không gian thế giới. Điểm trong hệ tọa độ camera $\mathbf{P}_C$ sau đó được chiếu lên mặt phẳng ảnh thông qua ma trận nội hàm $\mathbf{K}$ (intrinsic parameters), tạo ra tọa độ điểm ảnh $\mathbf{p} = [u, v]^T$. Toàn bộ quá trình này được mô tả bằng phương trình tọa độ đồng nhất:

$$s \begin{bmatrix} u \\ v \\ 1 \end{bmatrix} = \mathbf{K} \begin{bmatrix} \mathbf{R} & \mathbf{t} \end{bmatrix} \begin{bmatrix} X_W \\ Y_W \\ Z_W \\ 1 \end{bmatrix}$$

Trong đó, chiều sâu $s$ chính là tọa độ $Z_C$ của điểm ảnh trong hệ camera. Ma trận nội hàm $\mathbf{K}$ chứa các thông số vật lý cốt lõi của thấu kính và cảm biến, bao gồm tiêu cự $f_x, f_y$ được tính bằng đơn vị pixel, và tọa độ điểm chính (principal point) $c_x, c_y$ thường nằm gần trung tâm bức ảnh.

Trong thực tế, các ống kính quang học không bao giờ tuân theo hoàn hảo mô hình lỗ kim, sinh ra các hiện tượng biến dạng hình học (distortion). Độ méo xuyên tâm (radial distortion) làm các đường thẳng bị uốn cong ở rìa ảnh do hình dạng thấu kính, trong khi độ méo tiếp tuyến (tangential distortion) xảy ra do sự không song song tuyệt đối giữa thấu kính và cảm biến hình ảnh. Quá trình hiệu chuẩn camera (camera calibration) áp dụng các mô hình như Brown-Conrady để ước lượng các hệ số méo $k_1, k_2, k_3$ và $p_1, p_2$. Mọi thuật toán đo đạc 3D đều phải xử lý giải nén độ méo (undistortion) để đưa điểm ảnh về trạng thái lỗ kim tuyến tính lý tưởng trước khi tính toán.

Quá trình chiếu ngược (back-projection) từ điểm ảnh 2D về không gian 3D yêu cầu nghịch đảo ma trận nội hàm $\mathbf{K}^{-1}$ và bắt buộc phải có giá trị chiều sâu $Z$ được cung cấp từ một nguồn khác. Phương trình chiếu ngược tạo ra một vector tia sáng trong không gian $\mathbf{P}_C = Z \mathbf{K}^{-1} [u, v, 1]^T$. Sai số trong quá trình hiệu chuẩn có tác động hủy diệt đối với kết quả đo lường. Nếu tiêu cự $f_x$ bị ước lượng sai lệch $2\%$, toàn bộ mạng lưới không gian chiếu ngược sẽ bị thu nhỏ hoặc phóng to tương ứng, trực tiếp làm sai lệch kết quả đo khoảng cách dựa trên kích thước biểu kiến. Sai số tại điểm chính $c_x, c_y$ sẽ làm chệch vector tia sáng, gây ra sai số định vị tâm vật thể theo phương ngang và dọc, đặc biệt khuếch đại ở khoảng cách xa.

## 3\. Monocular Object Detection

Việc trích xuất thông tin 2D của đối tượng là lớp xử lý ngữ nghĩa đầu tiên định hình cách hệ thống khôi phục chiều không gian thứ ba. Đầu ra của các thuật toán nhận diện 2D quyết định tính chất và giới hạn của các suy diễn hình học tiếp theo.

Hộp giới hạn 2D (2D bounding box) là đầu ra cơ bản nhất, biểu diễn vật thể bằng bốn giá trị tọa độ $[u_{min}, v_{min}, u_{max}, v_{max}]$. Dù tính toán cực kỳ nhanh, 2D bounding box lại bộc lộ nhiều điểm yếu chí mạng trong đo đạc 3D. Hộp giới hạn rất dễ bị biến dạng bởi hiện tượng cắt xén ở viền ảnh (truncation) hoặc che khuất một phần (occlusion). Khi điều này xảy ra, kích thước của hộp 2D không còn tương quan với khoảng cách vật lý thực tế, khiến các phương pháp ước lượng độ sâu dựa trên kích thước biểu kiến bị sụp đổ hoàn toàn.

Phân đoạn thực thể (Instance segmentation) cung cấp một lớp mặt nạ (mask) bao phủ chính xác từng pixel thuộc về đối tượng, loại bỏ hoàn toàn nhiễu từ bối cảnh nền. Đối với bài toán đo đạc 3D, mặt nạ phân đoạn là công cụ vô giá khi kết hợp với các mô hình ước lượng độ sâu đơn kính. Nó cho phép hệ thống chỉ lấy trung bình các giá trị chiều sâu của các pixel thực sự thuộc về bề mặt đối tượng, tránh hiện tượng rò rỉ độ sâu (depth bleeding) ở phần rìa nơi đối tượng tiếp giáp với nền ở xa.

Nhận diện điểm đặc trưng (Keypoint detection) là cấp độ biểu diễn 2D phức tạp và có giá trị hình học cao nhất. Thay vì một hộp bao bọc chung chung, hệ thống nhận diện tọa độ của các điểm mang ý nghĩa cấu trúc không gian, ví dụ như 8 đỉnh của hộp giới hạn 3D được chiếu xuống 2D, các khớp xương của con người, hoặc các chi tiết đặc thù của xe (tâm bánh xe, viền đèn). Keypoint detection duy trì tính nhất quán về mặt hình học tô-pô bất chấp góc nhìn phối cảnh (perspective distortion). Điều này khiến keypoint trở thành đầu vào bắt buộc cho các thuật toán giải mã tư thế 6 chiều như PnP, nơi sự tương ứng điểm 1-1 giữa 2D và 3D định đoạt độ chính xác của toàn bộ hệ thống.

## 4\. Monocular Distance/Depth Estimation

Việc phục hồi chiều sâu từ một camera duy nhất đã tiến hóa từ các ràng buộc hình học khắt khe sang khả năng khái quát hóa vượt trội của trí tuệ nhân tạo.

Các phương pháp hình học cổ điển (classical geometric methods) phụ thuộc hoàn toàn vào tiên nghiệm về kích thước đối tượng (known-object-size methods). Dựa trên nguyên lý tam giác đồng dạng, nếu biết chiều cao thực tế $H$ của đối tượng và chiều cao biểu kiến trên ảnh $h$ (tính bằng pixel), khoảng cách $Z$ được tính xấp xỉ bằng $Z = (f \cdot H) / h$. Mặc dù tính toán tức thời, phương pháp này đòi hỏi vật thể không bị che khuất và bề mặt quan sát phải song song với mặt phẳng ảnh. Một vật thể xoay góc nghiêng (pitch/yaw) sẽ làm giảm kích thước biểu kiến $h$, khiến thuật toán tính khoảng cách xa hơn thực tế.

Phương pháp sử dụng mặt phẳng nền (ground-plane methods) giải quyết khoảng cách thông qua ràng buộc của bề mặt di chuyển. Dựa vào tọa độ pixel $v$ tại điểm tiếp xúc giữa vật thể và mặt đất, kết hợp với chiều cao lắp đặt camera $h_c$ và góc cúi $pitch$, hệ thống sử dụng hệ thức lượng để suy ra khoảng cách. Phương pháp này cực kỳ phổ biến trong hệ thống hỗ trợ lái xe nâng cao (ADAS), tuy nhiên nó rất nhạy cảm với độ gồ ghề của địa hình và dao động của hệ thống treo (suspension) khi xe tăng tốc hay phanh gấp.

Với sự trỗi dậy của học sâu, sự phân định giữa độ sâu tương đối (relative depth) và độ sâu tuyệt đối (metric depth) trở nên rõ ràng. Độ sâu tương đối bảo toàn thứ tự không gian trước-sau và hình thái bề mặt nhưng thiếu thang đo chuẩn, trong khi độ sâu tuyệt đối cung cấp giá trị mét chính xác, một bài toán được giải quyết thông qua việc mô hình hóa các manh mối phối cảnh và quy mô từ hàng triệu hình ảnh.

Giai đoạn 2022--2026 đánh dấu kỷ nguyên của các mô hình nền tảng (Foundation Models) cho Monocular Metric Depth. Các mô hình như Metric3D v2, UniDepthV2 và Depth Anything V2 đã thiết lập các chuẩn mực mới. Metric3D v2 (2024) giải quyết triệt để sự mơ hồ về thước đo do tiêu cự camera (focal length ambiguity) bằng cách đề xuất một phép biến đổi camera quy chuẩn (canonical camera transformation), đồng thời học chung tác vụ ước lượng bề mặt pháp tuyến (surface normal) để bảo toàn chi tiết hình học địa phương. Depth Anything V2 (2024) tận dụng bộ nội suy DINOv2 và một luồng huấn luyện đồ sộ dựa trên dữ liệu tổng hợp (synthetic data) sắc nét, giải quyết bài toán zero-shot metric depth với độ chính xác và biên dạng vật thể vượt trội. Đột phá về kiến trúc thuộc về UniDepthV2 (2025), khi mô hình này từ bỏ không gian tọa độ Cartesian truyền thống. UniDepthV2 thiết kế một mô hình tự nhắc (camera self-prompting mechanism) kết hợp không gian đầu ra giả cầu (pseudo-spherical) định nghĩa bởi góc phương vị, góc ngẩng và độ sâu $z_{log}$. Việc tách rời tối ưu hóa camera và độ sâu giúp ngăn chặn sự lan truyền gradient sai lệch, kết hợp với hàm mất mát bất biến hình học (geometric invariance loss) giúp bảo toàn sự nhất quán của hình dạng vật thể.

## 5\. Monocular 3D Object Detection

Phát hiện vật thể 3D từ ảnh đơn yêu cầu khôi phục trực tiếp một hộp giới hạn 3D (3D bounding box) bao quanh đối tượng, xác định đầy đủ tâm không gian $(X,Y,Z)$, kích thước vật lý $(W,H,D)$ và góc định hướng (orientation).

Các cấu trúc mạng trung tâm (Center-based architectures) thường khởi đầu bằng việc dự đoán tâm điểm chiếu 2D (projected center) của đối tượng trên mặt phẳng ảnh, sau đó kết hợp với các nhánh hồi quy (regression branches) để dự đoán chiều sâu $Z$, độ lệch tâm 3D, và kích thước. Tâm không gian $(X,Y,Z)$ cuối cùng được khôi phục bằng cách kết hợp chiều sâu $Z$ và nghịch đảo ma trận nội hàm $\mathbf{K}^{-1}$ với tọa độ tâm 2D.

Sự xuất hiện của kiến trúc Transformer đã tái định hình bài toán này. Các mô hình như MonoDETR thiết kế các bộ mã hóa nhận biết chiều sâu (depth-aware transformers). Thay vì dựa vào việc trích xuất đặc trưng khu vực cục bộ (RoI), Transformer tận dụng cơ chế tự chú ý (self-attention) trên toàn cục bức ảnh để phân tích sự tương tác giữa vật thể và các manh mối bối cảnh (contextual cues) ở xa như vạch kẻ đường, kích thước xe xung quanh. MonoDETR không cần dữ liệu độ sâu dày đặc bổ sung mà vẫn đạt hiệu năng hàng đầu theo thời gian thực.

Bên cạnh cải tiến kiến trúc, các chiến lược khai thác chiều sâu linh hoạt cũng được đề xuất. MonoCD (Monocular 3D Object Detection with Complementary Depths) chỉ ra rằng việc sử dụng nhiều bộ dự đoán chiều sâu cục bộ thường gặp chung một sai số cùng dấu, ngăn cản khả năng triệt tiêu lỗi qua ensemble. MonoCD giới thiệu nhánh độ sâu bổ sung toàn cục (complementary depth branch), khai thác thông tin từ toàn bộ ảnh để giảm tính tương quan lỗi giữa các dự đoán, giúp đẩy độ chính xác trung bình (AP3D) lên một mức mới trên tập dữ liệu KITTI.

Một bước tiến đáng kể khác là framework RARE (Learn-to-Rank and Retrieve) vào năm 2026. Các thuật toán truyền thống thường dự đoán điểm số phân loại (classification score) độc lập với chất lượng hộp 3D, dẫn đến việc các hộp 3D kém chính xác lại được giữ lại do điểm phân loại cao. RARE khắc phục triệt để vấn đề này thông qua cơ chế xếp hạng (Learn-to-Rank), kết nối điểm số tin cậy trực tiếp với chất lượng hình học của dự đoán, từ đó cải thiện hệ số tương quan (Spearman/Pearson) và tăng đáng kể độ chính xác 3D trên nuScenes và KITTI. Mặc dù vậy, điểm số AP3D của hạng mục Car (Moderate) trên KITTI của các mô hình SOTA (khoảng 16-20%) vẫn phản ánh sự chênh lệch to lớn so với cảm biến LiDAR.

## 6\. 6D Object Pose Estimation

Xác định tư thế 6 bậc tự do (6D pose estimation) đóng vai trò sống còn trong các tác vụ tương tác vật lý như robot lắp ráp công nghiệp hoặc thực tế tăng cường (AR). Thay vì chỉ ước lượng một hộp giới hạn chung chung, 6D pose tính toán chính xác 3 bậc tịnh tiến và 3 bậc xoay của đối tượng.

Thuật toán Perspective-n-Point (PnP) là cầu nối toán học kinh điển giữa 2D và 3D. Khi một mạng nơ-ron nhận diện thành công các điểm đặc trưng 2D trên ảnh (2D keypoints) và mô hình CAD 3D vật lý của đối tượng đã được biết trước, PnP sẽ tính toán tư thế camera (hoặc tư thế vật thể) sao cho việc chiếu các đỉnh 3D lên mặt phẳng 2D tạo ra sai số tái chiếu (reprojection error) nhỏ nhất.

Sự lựa chọn bộ giải PnP quyết định tính mạnh mẽ của hệ thống. EPnP (Efficient PnP) là một phương pháp tiệm cận tuyến tính với độ phức tạp $O(n)$, biểu diễn tất cả các điểm 3D thông qua 4 điểm điều khiển ảo (virtual control points). Dù cực kỳ nhanh, EPnP dễ bị mất ổn định trước các nhiễu tọa độ 2D. Trong khi đó, SQPnP (Sequential Quadratic Programming PnP) đúc kết bài toán dưới dạng quy hoạch toàn phương có ràng buộc (QCQP). Mặc dù đòi hỏi chi phí tính toán cao hơn đôi chút, SQPnP đảm bảo việc hội tụ tới nghiệm tối ưu toàn cục và thể hiện tính chống nhiễu vượt trội trong môi trường thực tế. Cả hai phương pháp thường được bao bọc trong vòng lặp RANSAC để loại bỏ các điểm tương ứng sai (outliers).

6D Pose chia thành hai bài toán theo mức độ thông tin tiên nghiệm. Định vị mức cá thể (Instance-level pose estimation) là khi robot được cung cấp chính xác mô hình CAD của vật thể cần thao tác (ví dụ: một mã phụ tùng cụ thể). Các mô hình như OPFormer và FoundationPose sử dụng Transformer để so khớp đặc trưng mô-đun (patch descriptors) giữa hình ảnh thực tế và các mẫu render từ mô hình CAD để tạo tập điểm tương ứng mật độ cao, từ đó giải PnP chính xác. Ngược lại, định vị mức phân lớp (Category-level pose estimation) không có mô hình CAD cụ thể mà chỉ có hình dáng trung bình của một chủng loại (ví dụ: "cái cốc"). Tác vụ này khó khăn hơn nhiều vì hệ thống phải đồng thời giải quyết biến dạng hình dạng (shape deformation) để quy chuẩn hóa vật thể trước khi có thể ước lượng tư thế.

Việc lựa chọn giữa mạng Depth Estimation và PnP phụ thuộc vào cự ly và thông tin prior. PnP phù hợp tuyệt đối cho môi trường cự ly gần (ví dụ: cánh tay robot gắp vật 0.5-2m) nơi đối tượng rõ nét, ít bị che khuất, và mô hình vật lý hoàn toàn xác định. Ngược lại, Depth Estimation tỏa sáng trong môi trường ngoài trời, cự ly xa, hoặc bối cảnh tự do (model-free) khi không có bất kỳ mô hình CAD nào được cung cấp.

## 7\. Physical Size Estimation

Để chuyển đổi từ pixel sang mét vuông (hoặc mét khối) bằng camera đơn, hệ thống phải giải nén sự bện chặt giữa kích thước biểu kiến, kích thước vật lý và khoảng cách.

Khi kích thước vật lý đã biết (known dimensions), việc ước lượng kích thước vật lý là không cần thiết, bài toán suy biến thành quá trình định vị khoảng cách thông qua tỷ lệ hình học. Tuy nhiên, trong bài toán kích thước vật thể chưa biết (unknown object dimensions), sự vắng mặt của tri thức tiên nghiệm khiến hệ thống rơi vào cạm bẫy scale ambiguity. Để giải quyết, mô hình deep learning buộc phải học các tỷ lệ tự nhiên từ bộ dữ liệu. Nó trích xuất các manh mối cấu trúc tinh vi như kích thước bánh xe, khoảng cách tay nắm cửa, hoặc kết cấu bề mặt để ngầm suy ra kích cỡ thực tế.

Sự ước lượng đồng thời cả khoảng cách và kích thước vật lý là khả thi khi có ràng buộc thứ ba: Ràng buộc mặt phẳng đất (Ground plane prior). Nếu mạng phát hiện điểm chạm đất của vật thể, góc pitch camera lập tức khóa cứng tọa độ $Z$. Một khi $Z$ đã được ấn định, chiều rộng $W$ và chiều cao $H$ có thể được nội suy ngược thông qua góc nhìn (FOV) và số lượng pixel bị chiếm dụng trên màn hình.

Bên cạnh khoảng cách, góc nhìn phối cảnh (perspective) và hướng xoay vật thể (object orientation) đóng vai trò quyết định. Một chiếc xe bị quan sát từ một góc ngẫu nhiên (yaw angle) sẽ thay đổi liên tục tỷ lệ khung hình biểu kiến. Việc thất bại trong việc đánh giá đúng góc xoay sẽ dẫn đến việc thuật toán nhầm lẫn giữa chiều dài $L$ và chiều rộng $W$, khiến toàn bộ sự lan truyền kích thước vật lý bị sai lệch.

## 8\. Ground-Plane / World-Coordinate Localization

Trong ứng dụng camera giám sát đô thị và hệ thống hỗ trợ tự lái xe, mọi thực thể thường được giả định hoạt động trên một mặt phẳng hai chiều, đơn giản hóa đáng kể bài toán định vị không gian.

Bề mặt phẳng trong không gian 3D được biểu diễn qua phương trình $\mathbf{n}^T \mathbf{P}_W + d = 0$. Mối quan hệ hình học chiếu từ mặt phẳng đất 3D vào mặt phẳng ảnh 2D được liên kết chuẩn xác thông qua một ma trận Homography $\mathbf{H}_{3 \times 3}$. Bằng cách nghịch đảo ma trận này, $\mathbf{p}_{ground} = \mathbf{H}^{-1} \mathbf{p}_{image}$, mọi tọa độ pixel (ví dụ điểm tâm đáy của bounding box) có thể được ánh xạ trực tiếp thành tọa độ thực địa dưới dạng bản đồ từ trên xuống (bird's-eye view).

Quá trình định vị bị chi phối bởi các tham số ngoại hàm của camera: chiều cao $h_c$, góc cúi (pitch) $\theta$, và góc nghiêng (roll) $\phi$. Ở trạng thái lý tưởng tĩnh, phương trình lượng giác cung cấp tọa độ $Z$ sắc nét. Tuy nhiên, trong thực tế chuyển động, gia tốc của xe khiến góc pitch dao động mạnh (xe chúc mũi khi phanh, ngóc đầu khi tăng tốc). Sự dao động này phá vỡ giả định tĩnh của ma trận biến đổi, đòi hỏi các thuật toán bù trừ ngoại hàm liên tục (online extrinsic calibration) thường thông qua phân tích đường chân trời (horizon line) hoặc sử dụng bộ lọc Kalman kết hợp với cảm biến gia tốc.

Việc chuyển đổi từ hệ tọa độ camera sang tọa độ thế giới (ví dụ: hệ quy chiếu bản đồ toàn cầu hoặc tọa độ tĩnh của bãi đỗ xe) được hoàn tất bằng công thức $\mathbf{P}_W = \mathbf{R}_{W \leftarrow C} \mathbf{P}_C + \mathbf{t}_{W \leftarrow C}$. Điều này cho phép đồng bộ hóa dữ liệu từ nhiều camera đơn phân tán thành một mô hình không gian duy nhất.

## 9\. Hybrid Approaches

Việc kết hợp nhiều luồng thông tin tạo ra các kiến trúc lai (hybrid pipelines) cân bằng giữa chi phí tính toán và độ chính xác.

| **Pipeline Cốt Lõi**         | **Đặc Trưng Đầu Vào & Đầu Ra** | **Ưu Điểm Nổi Bật** | **Hạn Chế Trọng Yếu** | **Ứng Dụng Thực Tiễn** |
| ---------------------------- | ------------------------------ | ------------------- | --------------------- | ---------------------- |
| **Detection + Ground Plane** |

**In:** RGB + Camera Pitch/Height.

**Out:** Tọa độ 3D trên mặt phẳng.

| Tính toán cực nhẹ, có thể đạt >60 FPS trên CPU thường. Dễ dàng triển khai. | Phá sản hoàn toàn nếu địa hình nhấp nhô hoặc góc pitch dao động. Không có 3D Bbox. | Camera giám sát giao thông, ADAS sơ cấp, phân tích lưu lượng. |
| **Detection + Metric Depth** |

**In:** RGB.

**Out:** 2D Bbox + Metric Point Cloud.

| Khả năng zero-shot mạnh mẽ trên bối cảnh chưa từng gặp. Không cần mô hình CAD. | Tốn nhiều tài nguyên bộ nhớ cho mô hình nền tảng. Hiện tượng trôi dạt tỷ lệ ở vùng viền ảnh. | Robot thám hiểm tự trị (model-free), định hướng tránh vật cản. |
| **Detection + Keypoints + PnP** |

**In:** RGB + 3D CAD Model.

**Out:** 6D Pose hoàn chỉnh.

| Cung cấp độ chính xác định vị và góc xoay milimet. Tối ưu toán học khắt khe (SQPnP). | Yêu cầu tiên quyết phải có file CAD vật lý. Nhạy cảm khi vật thể bị che khuất làm mất keypoints. | Robotic Bin Picking (robot gắp thả công nghiệp), AR/VR. |
| **Monocular Depth + 3D Detection** |

**In:** RGB.

**Out:** 3D Bounding Box (MonoDETR, RARE).

| Giải pháp End-to-end cân bằng tốt. Cơ chế Attention giúp xử lý đối tượng bị che khuất. | Bắt buộc huấn luyện trên dữ liệu LiDAR dồi dào. Domain gap lớn khi đổi loại camera. | Xe tự hành (Autonomous Driving), cảm biến môi trường động. |

## 10\. Single Image vs Monocular Video

Khi tiến động từ ảnh tĩnh sang luồng video liên tục (monocular video), thông tin thời gian (temporal information) trở thành chìa khóa để giảm bớt sự không chắc chắn hình học.

Các hệ thống Visual SLAM (Simultaneous Localization and Mapping) như ORB-SLAM3 tận dụng video để đồng thời xây dựng bản đồ 3D và theo dõi quỹ đạo thiết bị. Thuật toán phát hiện, so khớp và theo dõi các điểm đặc trưng (FAST, ORB) qua hàng loạt khung hình, tối ưu hóa toàn cục thông qua Bundle Adjustment. Tuy nhiên, về mặt toán học, **monocular video thuần túy KHÔNG thể tự giải quyết sự mơ hồ về tỷ lệ (Scale Ambiguity)**. Quỹ đạo và bản đồ được tạo ra chỉ mang tính tương đối (up-to-scale). Một hệ thống SLAM đơn kính không thể phân biệt giữa việc di chuyển 1 mét trong một căn phòng nhỏ hay 10 mét trong một nhà kho khổng lồ có kết cấu tỷ lệ tương đương. Hơn thế nữa, theo thời gian, tỷ lệ này sẽ trôi dạt (scale drift) dẫn đến việc không gian bị bóp méo.

Để đưa tỷ lệ về giá trị mét thực tế, video phải được lai ghép với các nguồn thông tin khác:

1.  **Visual-Inertial Odometry (VIO):** Cảm biến IMU cung cấp các giá trị gia tốc tuyến tính và vận tốc góc. Gia tốc trọng trường tạo ra một tham chiếu hướng dọc, trong khi sự biến thiên gia tốc tịnh tiến cho phép thuật toán khóa chặt metric scale của quỹ đạo camera.

2.  **Wheel Odometry:** Tích hợp vận tốc vòng quay của bánh xe cung cấp trực tiếp độ dời vật lý.

3.  **Temporal Depth Estimation:** Các mạng nơ-ron chuyên xử lý video (như ManyDepth2) sử dụng trạng thái ẩn (hidden states) để học tính nhất quán qua các khung hình, đồng thời sử dụng tri thức học sâu để áp đặt các mốc tỷ lệ vào cấu trúc cảnh vật.

## 11\. Accuracy và Error Analysis

Độ chính xác của đo đạc 3D đơn kính không duy trì tính tuyến tính mà suy thoái rất mạnh theo khoảng cách. Phân tích lan truyền sai số (Error Propagation) là cơ sở vật lý giải thích hiện tượng này.

Sự lan truyền sai số khoảng cách $\Delta Z$ bắt nguồn từ nguyên lý cơ bản $Z = f \cdot (H / h)$. Thông qua đạo hàm riêng, sai số toàn phần được phát biểu:

$$\Delta Z = \left\vert{} \frac{\partial Z}{\partial f} \right\vert{} \Delta f + \left\vert{} \frac{\partial Z}{\partial H} \right\vert{} \Delta H + \left\vert{} \frac{\partial Z}{\partial h} \right\vert{} \Delta h$$

Thành phần nguy hiểm nhất nằm ở sai số trên mặt phẳng ảnh $\Delta h$ (sai số từ thuật toán bounding box hoặc keypoint). Ta có $\frac{\partial Z}{\partial h} = -\frac{f H}{h^2}$. Vì kích thước biểu kiến $h$ tỷ lệ nghịch với $Z$ ($h \propto \frac{1}{Z}$), nên đạo hàm trở thành tỷ lệ thuận với bình phương khoảng cách: $\Delta Z \propto Z^2 \cdot \Delta h$. Điều này giải thích quy luật toán học cốt lõi: một sai lệch 1 pixel trên ảnh chỉ gây ra sai số vài milimet ở cự ly 1 mét, nhưng sẽ khuyếch đại thành sai số hàng mét hoặc chục mét ở cự ly 50 mét.

Sai số định vị 3D (3D localization error) không chỉ đến từ độ sâu $Z$. Khi nghịch đảo ma trận nội hàm, $\mathbf{X} = Z \cdot (u - c_x) / f_x$, bất kỳ sai số nhỏ nào trong việc xác định điểm chính $c_x$ (do hiệu chuẩn kém hoặc thấu kính lỏng lẻo) sẽ trực tiếp dịch chuyển tia sáng. Ở khoảng cách xa, sai số góc win nhỏ này sẽ bành trướng thành độ lệch phương ngang khổng lồ. Sự giãn nở nhiệt của thấu kính có thể làm biến đổi tiêu cự $f_x$, sinh ra lỗi tỷ lệ vĩnh viễn trên mọi hệ thống neural network được huấn luyện trên môi trường lý tưởng.

Lỗi định hướng (Pose error - Pitch, Yaw, Roll) đối với monocular camera phụ thuộc trực tiếp vào sự phân giải sắc nét của viền đối tượng. Khác với LiDAR đo trực tiếp sự chênh lệch độ sâu trên bề mặt, camera chỉ dựa vào hình chiếu phối cảnh của xe để đoán hướng xoay. Nếu xe bị che khuất hoặc thiếu chi tiết phân biệt (textureless), lỗi định hướng (đặc biệt là Yaw angle) sẽ vọt lên rất cao, phá vỡ ước lượng kích thước vật lý không gian.

## 12\. Dataset và Benchmark

Tiến bộ của Monocular 3D Perception được lèo lái bởi kiến trúc của các bộ dữ liệu đồ sộ và các hệ quy chiếu đánh giá phức tạp.

| **Lĩnh Vực / Dataset**                    | **Nguồn Thông Tin & Đặc Tính**                                                          | **Thước Đo Đánh Giá (Metric & Benchmark)**                                                                                                                                    | **Đóng Góp Nổi Bật**                                                                              |
| ----------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Autonomous Driving (KITTI)**            | Ảnh RGB ban ngày + Point Cloud. Gắn nhãn 3D Bounding Box dày đặc ở cự ly <70m.          | **AP3D & APBEV:** Trung bình độ chính xác (Precision) tại mốc IoU=0.7 (xe ô tô) theo các độ khó Easy/Moderate/Hard.                                                           | Là nền tảng tiên phong, nhưng bộc lộ điểm yếu khi thiên lệch mạnh vào ánh sáng ban ngày.          |
| **Autonomous Driving (nuScenes / Waymo)** | Video liên tục, nhiều góc quay (360 độ), thời tiết đa dạng (mưa, đêm).                  | **NDS (nuScenes Detection Score):** Tổng hợp mAP cùng các sai số tịnh tiến (ATE), kích thước (ASE), hướng (AOE). **APH:** Benchmark của Waymo đánh giá mAP tích hợp góc xoay. | Mở khóa nghiên cứu temporal fusion (kết hợp chuỗi thời gian) và phát hiện môi trường khắc nghiệt. |
| **Metric Depth (NYUv2, ScanNet)**         | RGB + Ground Truth Depth từ cảm biến Kinect/LiDAR.                                      | **RMSE, AbsRel (Absolute Relative Error):** Đo khoảng cách lỗi và tỷ lệ pixel $\delta < 1.25$.                                                                                | Chuẩn mực đánh giá zero-shot depth estimation trong môi trường kiến trúc phức tạp.                |
| **6D Pose Estimation (BOP Challenge)**    | LINEMOD, YCB-Video, và mới nhất BOP-Industrial 2025 (XYZ-IBD, IPD) chứa ảnh multi-view. | **VSD (Visible Surface Discrepancy), MSSD:** Đánh giá độ sai lệch không gian của các đỉnh bề mặt CAD model sau khi ráp pose.                                                  | Thúc đẩy các thuật toán PnP và model-based matching vượt rào cản ứng dụng công nghiệp nặng.       |

## 13\. Các Phương Pháp Hiện Đại 2022--2026

Giai đoạn 2022--2026 chứng kiến sự dịch chuyển kiến trúc từ mạng nơ-ron tích chập (CNNs) sang Transformers và các nền tảng học máy khổng lồ (Foundation Models).

Đối với Metric Depth Estimation, xu hướng chuyển từ các mô hình đào tạo theo từng dataset sang các mô hình khái quát hóa. Các mô hình Depth Foundation tận dụng kiến trúc ViT (như DINOv2) và học từ nguồn dữ liệu hỗn hợp (mixed datasets) chứa hàng chục triệu ảnh thực tế và ảnh đồ họa (synthetic). Những tinh chỉnh toán học về không gian chiếu, như hệ trục pseudo-spherical của UniDepthV2 hay không gian camera quy chuẩn của Metric3D v2, cho phép mô hình đánh bại sự giới hạn về thiết bị camera (domain invariant) để sinh ra metric depth zero-shot sắc bén.

Trong phân khúc Monocular 3D Detection, mô hình như MonoDETR, RARE kết hợp cơ chế chú ý (attention mechanisms) trực tiếp lên quá trình định hình cấu trúc không gian. Cross-attention được dùng để truy vấn (query) các khu vực chứa đối tượng trong khi self-attention giúp mô hình "nhìn" bối cảnh rộng lớn để hiệu chỉnh depth.

Đối với 6D Pose Estimation, các cách tiếp cận kinh điển (nhận diện keypoints tĩnh) dần được thay thế bằng template matching dựa trên AI. FoundationPose và OPFormer sinh ra hàng ngàn góc nhìn render từ mô hình CAD, sau đó sử dụng Transformer để so khớp đặc trưng mô-đun (patch-wise matching) với ảnh chụp thực tế. Hệ thống này không cần đào tạo lại cho từng loại vật thể mới, tạo ra cuộc cách mạng thực sự cho môi trường sản xuất linh hoạt.

## 14\. Real-world Feasibility (Khả thi thực tế)

Khả năng thay thế các cảm biến LiDAR và Stereo của hệ thống đơn kính phụ thuộc trực tiếp vào phân khúc khoảng cách và điều kiện môi trường.

**Phân tích độ chính xác theo khoảng cách:**

- **0.5m -- 2m (Thao tác cơ khí, Gắp vật, AR):** Độ chính xác thực tế đạt mức milimet (1-5mm) và sai số góc chỉ dưới 1 độ. Tại cự ly này, đối tượng lấp đầy khung hình camera, cung cấp độ phân giải keypoint dày đặc cho các bộ giải toán tối ưu SQPnP. Monocular camera gần như có thể thay thế hoàn toàn cảm biến chiều sâu đắt tiền.

- **2m -- 5m (Giám sát, Robot di động trong nhà):** Sai số độ sâu tuyệt đối (metric error) dao động trong khoảng $2\% - 5\%$. Hệ thống có thể hoạt động ổn định nhưng yêu cầu thuật toán SLAM hoặc Ground-plane phụ trợ để hiệu chỉnh.

- **5m -- 10m (ADAS cơ bản, Xe tự hành tốc độ thấp):** Sai số độ sâu vọt lên $5\% - 10\%$. Bắt đầu xuất hiện sự bất ổn khi phân biệt các vật thể bị cắt xén (truncated) ở viền khung hình.

- **>10m (Xe tự hành cao tốc):** Độ chính xác suy giảm theo hàm mũ. Sai số vài mét là chuyện bình thường. Hệ thống monocular hiện tại không đủ đáp ứng tiêu chuẩn an toàn độc lập (safety-critical) và buộc phải giữ vai trò cảm biến dự phòng hoặc được kết hợp (fusion) với Radar/LiDAR.

**Các kịch bản hỏng hóc (Failure cases):** Thiếu sáng (low-light) và môi trường đêm vẫn là tử huyệt của hệ thống quang học; sự suy giảm viền cạnh và hiện tượng lóa sáng (glare) làm vô hiệu hóa cả hình học chiếu lẫn tri thức học sâu. Các bề mặt vật thể trong suốt hoặc có độ phản gương cao (reflective object) sẽ phá hủy hoàn toàn đặc trưng matching của 6D pose và độ tin cậy của mô hình chiều sâu. Hiện tượng bị che khuất cực độ (extreme occlusion >50%) khiến tâm vật thể 3D nằm ngoài vùng có thể dự đoán. Cuối cùng, các đối tượng có kích thước dị biệt (unknown size) gây bối rối cho mạng nơ-ron do chúng phụ thuộc quá mạnh vào prior kích thước trung bình đã được ghi nhớ từ tập huấn luyện.

## 15\. Edge/AIoT Deployment

Động lực chính duy trì nghiên cứu Monocular 3D perception là khả năng giảm thiểu phần cứng và chi phí năng lượng để triển khai trên hệ thống biên (Edge AI) và vạn vật kết nối (AIoT).

Mặc dù các Transformer mang lại hiệu năng đỉnh cao, chúng sở hữu lượng tham số khổng lồ, gây cản trở triển khai nguyên bản trên các máy tính nhúng. Các phần cứng như NVIDIA Jetson phụ thuộc sâu sắc vào kiến trúc tối ưu TensorRT, trong khi CPU nhúng sử dụng thư viện như OpenVINO và NNCF.

Việc hạ thấp độ chính xác dấu phẩy động xuống FP16 hoặc lượng tử hóa số nguyên (INT8 quantization) là quy trình bắt buộc để ép mô hình chạy ở mức thời gian thực. Chẳng hạn, phiên bản thu gọn (Small version) của mô hình Depth Anything V2 (khoảng 24.8M tham số) khi được tăng tốc qua OpenVINO có thể đáp ứng FPS cao với năng lượng cực thấp, lý tưởng cho máy bay không người lái (drone) hoặc robot AGV. Đối với các bài toán hình học cổ điển, thuật toán định vị PnP sử dụng thư viện OpenCV trên C++ có độ trễ chỉ vài mili-giây, chiếm một lượng CPU không đáng kể, làm cho nó trở thành mảnh ghép hoàn hảo cho các thiết bị công nghiệp hạn chế năng lực tính toán.

## 16\. Tổng Hợp Không Gian Nghiên Cứu

Bức tranh toàn cảnh về nhận thức không gian 3D từ một camera RGB là sự đan xen giữa các định lý quang học khắt khe và sức mạnh ước lượng của mạng học sâu.

| **Yếu Tố Phân Tích**        | **Tổng Kết Chuyên Sâu**                                                                                                                                                                                                                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Bản chất Fundamental**    | Dùng một camera duy nhất là việc cố gắng nội suy không gian từ một hàm chiếu không có tính nghịch đảo (Scale Ambiguity). Mọi nguồn Metric Scale (đo lường mét) phải đến từ một trong ba ngõ: (1) Input vật lý (CAD/kích thước), (2) Prior hình học (Mặt đất/Camera extrinsic), hoặc (3) Learned prior (Mạng AI "ghi nhớ" quy mô bối cảnh). |
| **Pipeline Đơn giản**       | **2D Box + Ground Plane:** Nhanh, nhẹ, triển khai dễ dàng, nhưng độ tin cậy thấp, dễ phá sản bởi địa hình.                                                                                                                                                                                                                                 |
| **Pipeline Phức tạp**       | **Transformer 3D Box & Depth Foundation:** Khả năng zero-shot xuất sắc, tự động nhận biết chiều sâu, nhưng yêu cầu GPU mạnh và vẫn bị nhiễu ở khoảng cách lớn.                                                                                                                                                                             |
| **Pipeline Công nghiệp**    | **Keypoints + 3D CAD + SQPnP:** Tối ưu hóa toán học mạnh, chuẩn xác milimet, nhưng đòi hỏi biết trước hình dáng đối tượng và giới hạn ở cự ly gần.                                                                                                                                                                                         |
| **Chi phí Tính toán**       | Trải rộng từ các phép toán đại số ma trận mili-giây (EPnP) đến các phép nhân ma trận tự chú ý khổng lồ của ViT (tốn hàng GB VRAM). Các kỹ thuật lượng tử hóa (INT8, FP16) là chìa khóa triển khai thực tế.                                                                                                                                 |
| **Khoảng trống Nghiên cứu** |

Domain gap (sự chênh lệch giữa ngày/đêm, điều kiện thời tiết), sự lan truyền sai số khuếch đại theo hàm bậc hai của khoảng cách, và thiếu một cơ chế đánh giá độ không chắc chắn (uncertainty representation) vững chắc khiến monocular 3D chưa đủ khả năng thay thế LiDAR trong các kịch bản an toàn tuyệt đối.

|

Đích đến của Monocular 3D Perception không phải là thay thế hoàn toàn các cảm biến đa chiều trong môi trường sống còn, mà là cung cấp một giải pháp định vị không gian độc lập, cực kỳ linh hoạt, chi phí thấp, nhằm mở rộng nhận thức thông minh (intelligent perception) cho hàng tỷ thiết bị tự trị vừa và nhỏ trong tương lai.
