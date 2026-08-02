-- MariaDB dump 10.19-11.3.2-MariaDB, for Win64 (AMD64)
--
-- Host: zephyr.proxy.rlwy.net    Database: railway
-- ------------------------------------------------------
-- Server version	9.4.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tasks`
--

DROP TABLE IF EXISTS `tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `content` varchar(255) NOT NULL,
  `action` text NOT NULL,
  `status` varchar(50) DEFAULT 'Done',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `ticket_id` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tasks`
--

LOCK TABLES `tasks` WRITE;
/*!40000 ALTER TABLE `tasks` DISABLE KEYS */;
INSERT INTO `tasks` VALUES
(1,'Form 1: Phân loại chi phí bảo hành','Admin đã đánh dấu hoàn thành','Done','2026-05-29 07:59:03',NULL),
(2,'Form 5: Đăng ký tài khoản user nội bộ Gree','Admin đã đánh dấu hoàn thành','Done','2026-06-01 02:40:54',NULL),
(3,'Form 5: Đăng ký tài khoản user nội bộ Gree','Đã khóa user Tuyên','Done','2026-06-02 08:13:09',NULL),
(4,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-03 06:58:24',NULL),
(5,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-04 04:50:48',NULL),
(6,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-09 01:39:27',NULL),
(7,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:03:02',NULL),
(8,'Form 6: Khai báo Model cho Import Hồ sơ máy','Admin đã đánh dấu hoàn thành','Done','2026-06-09 09:05:34',NULL),
(9,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:12:21',NULL),
(10,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:16:32',NULL),
(11,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:17:07',NULL),
(12,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:17:37',NULL),
(13,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:19:13',NULL),
(14,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:19:42',NULL),
(15,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model đã có sẵn, đã bật import theo yêu cầu','Done','2026-06-09 09:20:12',NULL),
(16,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-10 07:50:26',NULL),
(17,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-10 09:33:42',NULL),
(18,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-12 04:42:03',NULL),
(19,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-12 06:57:38',NULL),
(20,'Form 5: Đăng ký tài khoản user nội bộ Gree','Admin đã đánh dấu hoàn thành','Done','2026-06-15 10:02:22',NULL),
(21,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-16 03:57:14',NULL),
(22,'Hỗ trợ khởi tạo KH là Nhân viên mới trên hệ thống ERP','Admin đã đánh dấu hoàn thành','Done','2026-06-18 01:33:20','GREE-IT_202606_194'),
(23,'Tin nhắn chưa có ra khỏi hệ thống để đẩy qua bên NCC','Admin đã đánh dấu hoàn thành','Done','2026-06-18 01:36:01','GREE-IT_202606_868'),
(24,'Hỗ trợ phân quyền màn hình mới cho Admin RAC (Huỳnh Anh)','Admin đã đánh dấu hoàn thành','Done','2026-06-18 01:42:50','GREE-IT_202606_142'),
(25,'Hỗ trợ sale kích hoạt An Gia cho các trường hợp KH quên kích hoạt hoặc điền sai số điện thoại','Admin đã đánh dấu hoàn thành','Done','2026-06-19 03:54:23','GREE-IT_202606_572'),
(26,'Cập nhật thông tin trạm bảo hành BÙI CÔNG KHANH','Đã cập nhật:\ncũ: \n- Cơ Sở Điện Lạnh Khanh Tâm - Gia Lai\n- 171 Phan Đình Phùng, Phường Diên Hồng, Tỉnh Gia Lai\n\ny/c mới: \n- CÔNG TY TNHH MỘT THÀNH VIÊN KHANH TÂM - GIA LAI\n- 343 Phan Đình Phùng, Phường Diên Hồng, Tỉnh Gia Lai','Done','2026-06-19 04:05:27','GREE-IT_202606_191'),
(27,'Form 6: Khai báo Model cho Import Hồ sơ máy','Admin đã đánh dấu hoàn thành','Done','2026-06-19 08:25:46','GREE-IT_202606_791'),
(28,'Import hồ sơ máy ','Admin đã đánh dấu hoàn thành','Done','2026-06-22 06:20:42','GREE-IT_202606_257'),
(29,'Hỗ trợ khởi tạo Model cho Import Hồ sơ máy','Admin đã đánh dấu hoàn thành','Done','2026-06-22 09:49:29','GREE-IT_202606_949'),
(30,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-23 02:00:01','GREE-IT_202606_367'),
(31,'Cập nhật thời gian bảo hành 36 tháng cho dự án King Food Market','Admin đã đánh dấu hoàn thành','Done','2026-06-23 02:01:10','GREE-IT_202606_575'),
(32,'Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Ticket được tạo và hoàn thành ngay khi khởi tạo.','Done','2026-06-24 02:39:07','GREE-IT_202606_854'),
(33,'G-APP / Các yêu cầu hỗ trợ G-APP khác','Admin đã đánh dấu hoàn thành','Done','2026-06-24 03:26:29','GREE-IT_202606_678'),
(34,'G-APP / Tài khoản nội bộ','Admin đã đánh dấu hoàn thành','Done','2026-06-24 06:42:41','GREE-IT_202606_776'),
(35,'Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Ticket được tạo và hoàn thành ngay khi khởi tạo.','Done','2026-06-24 08:32:37','GREE-IT_202606_202'),
(36,'Form 4: Đăng ký thông tin trạm bảo hành mới','Admin đã đánh dấu hoàn thành','Done','2026-06-24 08:48:36','GREE-IT_202606_535'),
(37,'Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Admin đã đánh dấu hoàn thành','Done','2026-06-24 08:50:13','GREE-IT_202606_202'),
(38,'Cập nhật chương trình VQMM trên hệ thống Gree App (start: 25/06)','Admin đã đánh dấu hoàn thành','Done','2026-06-25 01:00:43','GREE-IT_202606_560'),
(39,'Seri 3K4275B010514 không gửi sms warranty được ','06/02/2026 Serial được import vào hệ thống\n12/06/2026Thợ kích hoạt bảo hành\n16/06/2026 17:09 Ai đó update thông tin\n18/06/2026 22:26 Phúc resend SMS lần 1 → thất bại\n18/06/2026 22:28 Phúc update thông tin\n18/06/2026 22:29 Phúc resend SMS lần 2 → thất bại\n23/06/2026 14:21 Phúc resend SMS lần 3 → thất bại \n\n\nNGUYÊN NHÂN LỖI:\nThiếu các thông tin C1, Kênh PP, Ngày xuất kho nên serial bị đánh dấu chặn gởi sms\n','Done','2026-06-25 03:32:17','GREE-IT_202606_127'),
(40,'Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Ticket được tạo và hoàn thành ngay khi khởi tạo.','Done','2026-06-25 03:46:58','GREE-IT_202606_167'),
(41,'CA BẢO HÀNH_CHI PHÍ ĐI LẠI TÍNH 2 LẦN','Hi Phượng,\nNam xác nhận Xuân có nhờ hỗ trợ đóng ca MTNA2026040578 do không duyệt 2 bước linh kiện được để hoàn thành ca vào ngày (15h51 20/05/2026)\n','Done','2026-06-25 06:36:57','GREE-IT_202606_309'),
(42,'Giao diện của khách không có banner chương trình VQMM','Admin đã đánh dấu hoàn thành','Done','2026-06-25 07:14:05','GREE-IT_202606_451'),
(43,'Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Admin đã đánh dấu hoàn thành','Done','2026-06-25 08:06:56','GREE-IT_202606_185'),
(44,'Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Ticket được tạo và hoàn thành ngay khi khởi tạo.','Done','2026-06-25 08:32:10','GREE-IT_202606_514'),
(45,'Form 6: Khai báo Model cho Import Hồ sơ máy','Admin đã đánh dấu hoàn thành','Done','2026-06-25 09:40:29','GREE-IT_202606_696'),
(46,'Form 6: Khai báo Model cho Import Hồ sơ máy','Model này đã có','Done','2026-06-25 09:59:45','GREE-IT_202606_948'),
(47,'Admin hỗ trợ gia hạn kích hoạt An Gia (24h)','Admin đã đánh dấu hoàn thành','Done','2026-06-26 08:04:42','GREE-IT_202606_767'),
(48,'Kích hoạt BH vào PMBH cho KH Kingfood từ tháng 11 năm 2023 ','Admin đã đánh dấu hoàn thành','Done','2026-06-29 07:31:24','GREE-IT_202606_424'),
(49,'Khách C2 họ phản ánh vừa kích hoạt 10 bộ hàng BD được tính thưởng +200 gcoin/bộ, tuy nhiên vòng quay may mắn chỉ có 4 vòng.','Admin đã đánh dấu hoàn thành','Done','2026-06-29 07:34:48','GREE-IT_202606_444'),
(50,'Sales yêu cầu mở tài khoản nội bộ','Admin đã đánh dấu hoàn thành','Done','2026-06-29 07:48:46','GREE-IT_202606_385');
/*!40000 ALTER TABLE `tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ticket_messages`
--

DROP TABLE IF EXISTS `ticket_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ticket_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ticket_id` varchar(50) NOT NULL,
  `user` varchar(100) NOT NULL,
  `msg` text NOT NULL,
  `type` varchar(50) DEFAULT 'public',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ticket_id` (`ticket_id`),
  CONSTRAINT `ticket_messages_ibfk_1` FOREIGN KEY (`ticket_id`) REFERENCES `tickets` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=72 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ticket_messages`
--

LOCK TABLES `ticket_messages` WRITE;
/*!40000 ALTER TABLE `ticket_messages` DISABLE KEYS */;
INSERT INTO `ticket_messages` VALUES
(1,'GREE-IT_202605_398','Vương Trần','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Bao_Hanh\'.','public','2026-05-29 07:58:41'),
(2,'GREE-IT_202605_208','Vương Trần','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Bao_Hanh\'.','public','2026-05-29 09:49:09'),
(3,'GREE-IT_202606_942','Mr Hổ BH-RAC','Hệ thống: Ticket tự động được tạo từ form \'Dang_Ky_Tai_Khoan_User_Noi_Bo\'.','public','2026-06-01 02:35:11'),
(4,'GREE-IT_202606_845','Vương CAC','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Bao_Hanh\'.','public','2026-06-01 04:20:14'),
(5,'GREE-IT_202606_526','Trần Đức Toàn','Hệ thống: Ticket tự động được tạo từ form \'Dang_Ky_Tai_Khoan_User_Noi_Bo\'.','public','2026-06-02 03:37:57'),
(6,'GREE-IT_202606_526','Admin Nam','Đã khóa user Tuyên','public','2026-06-02 08:13:04'),
(7,'GREE-IT_202606_425','Phan Hoàng Phong','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-03 06:55:44'),
(8,'GREE-IT_202606_455','Luân BH - RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-04 04:48:24'),
(9,'GREE-IT_202606_197','Mr Thắng BH-RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-09 01:39:14'),
(10,'GREE-IT_202606_783','Ms Phượng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:00:01'),
(11,'GREE-IT_202606_600','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:00:54'),
(12,'GREE-IT_202606_600','Admin Nam','Model đã có sẵn, đã bật import theo yêu cầu','public','2026-06-09 09:02:57'),
(13,'GREE-IT_202606_174','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:08:39'),
(14,'GREE-IT_202606_703','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:09:06'),
(15,'GREE-IT_202606_295','Ms Phượng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:09:19'),
(16,'GREE-IT_202606_806','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:09:30'),
(17,'GREE-IT_202606_967','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:10:08'),
(18,'GREE-IT_202606_710','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:11:21'),
(19,'GREE-IT_202606_676','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:11:54'),
(20,'GREE-IT_202606_881','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-09 09:13:35'),
(21,'GREE-IT_202606_174','Admin Nam','Model này có khoảng trắng, em kiểm tra lại giúp anh','public','2026-06-09 09:21:04'),
(22,'GREE-IT_202606_171','Phan Huy Hoàng','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-10 07:48:08'),
(23,'GREE-IT_202606_171','Admin Nam','Bạn cập nhật nhầm CAC thành Kho RAC.\nTạo 2 lần điều chỉnh -1 RAC đã tạo và +1 CAC mới','public','2026-06-10 09:22:58'),
(24,'GREE-IT_202606_175','Mr Thắng BH-RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-10 09:30:37'),
(25,'GREE-IT_202606_858','Thắng RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-12 04:31:24'),
(26,'GREE-IT_202606_412','Khoa Bảo Hành CAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-12 06:49:35'),
(27,'GREE-IT_202606_679','Nguyễn Quang Tùng','Hệ thống: Ticket tự động được tạo từ form \'Dang_Ky_Tai_Khoan_User_Noi_Bo\'.','public','2026-06-15 09:41:17'),
(28,'GREE-IT_202606_489','Phan Hoàng Phong','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-16 03:57:00'),
(29,'GREE-IT_202606_191','Phan Hoàng Phong','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-17 10:07:46'),
(30,'GREE-IT_202606_194','Trần Thị Mai Thi','Hệ thống: Ticket tự động được tạo từ form \'ERP_Yeu_Cau_Tong_Hop\'.','public','2026-06-18 01:33:04'),
(31,'GREE-IT_202606_868','Phạm Văn Tâm','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-18 01:35:44'),
(32,'GREE-IT_202606_142','Trần Thị Mai Thi','Hệ thống: Ticket tự động được tạo từ form \'ERP_Yeu_Cau_Tong_Hop\'.','public','2026-06-18 01:41:19'),
(33,'GREE-IT_202606_572','Lệ Anh','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-19 03:54:11'),
(34,'GREE-IT_202606_575','Trần Dương Nhẫn','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-19 03:56:42'),
(35,'GREE-IT_202606_191','Admin Nam','Đã cập nhật:\ncũ: \n- Cơ Sở Điện Lạnh Khanh Tâm - Gia Lai\n- 171 Phan Đình Phùng, Phường Diên Hồng, Tỉnh Gia Lai\n\ny/c mới: \n- CÔNG TY TNHH MỘT THÀNH VIÊN KHANH TÂM - GIA LAI\n- 343 Phan Đình Phùng, Phường Diên Hồng, Tỉnh Gia Lai','public','2026-06-19 04:05:03'),
(36,'GREE-IT_202606_466','Phương Huỳnh','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-19 07:37:09'),
(37,'GREE-IT_202606_791','Phượng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-19 08:10:45'),
(38,'GREE-IT_202606_575','Admin Nam','Đang nhờ NCC (mr Tín Dev BSC) kiểm tra lỗi xử lý phần hiển thị thời gian bảo hành BSC','public','2026-06-19 08:27:06'),
(39,'GREE-IT_202606_257','PHƯỢNG BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-22 03:38:24'),
(40,'GREE-IT_202606_560','Lượng MKT','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-22 06:24:48'),
(41,'GREE-IT_202606_949','Phượng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-22 09:47:06'),
(42,'GREE-IT_202606_367','Phan Hoàng Phong','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-22 10:09:17'),
(43,'GREE-IT_202606_767','Vương Đình Tuấn','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-23 02:10:21'),
(44,'GREE-IT_202606_127','Hồng Phúc CS','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-23 07:46:57'),
(45,'GREE-IT_202606_854','Tuong BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Admin_Web_Noted_Log_Ho_Tro\'.','public','2026-06-24 02:39:07'),
(46,'GREE-IT_202606_854','Admin Nam','Sai nội dung chi phí đi lại ( 2 lần ) Admin hỗ trợ từ chối để cập nhật lại','public','2026-06-24 02:44:31'),
(47,'GREE-IT_202606_678','tuan.vuong@gree.com.vn','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-24 02:53:51'),
(48,'GREE-IT_202606_776','hiep.huynh@gmail.com','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-24 02:56:26'),
(49,'GREE-IT_202606_776','Admin Nam','* Thời gian yêu cầu: 23/06/2026\n* Loại tài khoản Admin: Sale\n* Loại tài khoản G-App: Sale Mini App\n* Tên đăng nhập: thang.nguyen\n* Họ và tên: Nguyễn Toàn Thắng\n* Số điện thoại: 84906119383\n* Văn phòng: Hải Phòng\n* BU: RAC\n* Phòng ban: Kinh Doanh\n* Chức danh: Staff\n* Vùng: North 2\n* Khu vực: Hải Phòng 1\n','public','2026-06-24 04:45:29'),
(50,'GREE-IT_202606_535','Nguyễn Vũ Luân','Hệ thống: Ticket tự động được tạo từ form \'Dang_Ky_Tram_Bao_Hanh_Moi\'.','public','2026-06-24 07:08:44'),
(51,'GREE-IT_202606_202','Tưởng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Admin_Web_Noted_Log_Ho_Tro\'.','public','2026-06-24 08:32:37'),
(52,'GREE-IT_202606_560','Admin Nam','@Le Quan Dat Dạ, hiện NCC đã submit phiên bản Zalo Mini App lên Zalo để chờ phê duyệt chức năng Vòng quay may mắn. (đêm qua 23h47). Hiện tại Zalo chưa duyệt\n\nTheo trao đổi, sau khi Zalo phê duyệt sẽ còn một số đầu việc cần phối hợp triển khai như:\n\n- Cập nhật source code và database trên môi trường Production.\n- Cấu hình chiến dịch vòng quay trên Admin.\n- Cấu hình giải thưởng, số lượng và điều kiện tham gia.\n- Cập nhật banner và nội dung hiển thị.\n- Bật chức năng trên Mini App.\n- Kiểm tra lại luồng kích hoạt bảo hành → nhận ticket → tham gia vòng quay → nhận thưởng. (nhờ anh NCC hỗ trợ cách kiểm tra để không ảnh hưởng tới dữ liệu đang chạy)\n\nNhờ Anh @Hiệu Đỗ (Dev App Gree)  hỗ trợ chia sẻ thêm checklist triển khai và các hạng mục cần phối hợp trước khi Go-live để các bên chủ động chuẩn bị và tránh thiếu sót trong quá trình vận hành.','public','2026-06-24 09:08:26'),
(53,'GREE-IT_202606_127','Admin Nam','06/02/2026 Serial được import vào hệ thống\n12/06/2026Thợ kích hoạt bảo hành\n16/06/2026 17:09 Ai đó update thông tin\n18/06/2026 22:26 Phúc resend SMS lần 1 → thất bại\n18/06/2026 22:28 Phúc update thông tin\n18/06/2026 22:29 Phúc resend SMS lần 2 → thất bại\n23/06/2026 14:21 Phúc resend SMS lần 3 → thất bại \n\n\nNGUYÊN NHÂN LỖI:\nThiếu các thông tin C1, Kênh PP, Ngày xuất kho nên serial bị đánh dấu chặn gởi sms\n','public','2026-06-25 03:22:27'),
(54,'GREE-IT_202606_767','Admin Nam','Chờ Sale phản hồi thời gian thích hợp gia hạn cho Khách hàng, mới xử lý gia hạn','public','2026-06-25 03:45:08'),
(55,'GREE-IT_202606_167','Mr Tưởng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Admin_Web_Noted_Log_Ho_Tro\'.','public','2026-06-25 03:46:58'),
(56,'GREE-IT_202606_309','Phượng BH RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-25 04:08:19'),
(57,'GREE-IT_202606_309','Admin Nam','Hi Phượng,\nNam xác nhận Xuân có nhờ hỗ trợ đóng ca MTNA2026040578 do không duyệt 2 bước linh kiện được để hoàn thành ca vào ngày (15h51 20/05/2026)\n','public','2026-06-25 06:36:51'),
(58,'GREE-IT_202606_451','Thắng Gree','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-25 07:13:49'),
(59,'GREE-IT_202606_185','Thắng RAC','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Dieu_Chinh_Ton_Kho\'.','public','2026-06-25 07:57:26'),
(60,'GREE-IT_202606_514','Ms Giàu CS','Hệ thống: Ticket tự động được tạo từ form \'Admin_Web_Noted_Log_Ho_Tro\'.','public','2026-06-25 08:32:10'),
(61,'GREE-IT_202606_696','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-25 09:24:11'),
(62,'GREE-IT_202606_948','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-25 09:43:20'),
(63,'GREE-IT_202606_832','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-25 09:43:52'),
(64,'GREE-IT_202606_349','Vũ XNK','Hệ thống: Ticket tự động được tạo từ form \'Khai_Bao_Model_Ho_So_May\'.','public','2026-06-25 09:45:00'),
(65,'GREE-IT_202606_349','Admin Nam','Thường model này a thấy nó có RF28WPd/NaA-M/I hoặc /O','public','2026-06-25 09:57:42'),
(66,'GREE-IT_202606_832','Admin Nam','Model này đã có','public','2026-06-25 09:58:56'),
(67,'GREE-IT_202606_444','Vũ Đạt Sale','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-26 00:57:49'),
(68,'GREE-IT_202606_424','Trần Dương Nhẫn','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-29 01:23:42'),
(69,'GREE-IT_202606_385','chung.ha@gree.com.vn','Hệ thống: Ticket tự động được tạo từ form \'GreeApp_Yeu_Cau_Tong_Hop\'.','public','2026-06-29 01:33:16'),
(70,'GREE-IT_202606_123','Trần Thị Mai Thi','Hệ thống: Ticket tự động được tạo từ form \'ERP_Yeu_Cau_Tong_Hop\'.','public','2026-06-29 02:14:10'),
(71,'GREE-IT_202606_988','Dương Chiếu Quốc','Hệ thống: Ticket tự động được tạo từ form \'Yeu_Cau_Tong_Hop_Khac\'.','public','2026-06-29 07:54:00');
/*!40000 ALTER TABLE `ticket_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tickets`
--

DROP TABLE IF EXISTS `tickets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tickets` (
  `id` varchar(50) NOT NULL,
  `subject` varchar(255) NOT NULL,
  `requester` varchar(100) NOT NULL,
  `status` varchar(50) DEFAULT 'Mới tạo',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `form_type` varchar(255) DEFAULT NULL,
  `form_data` json DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tickets`
--

LOCK TABLES `tickets` WRITE;
/*!40000 ALTER TABLE `tickets` DISABLE KEYS */;
INSERT INTO `tickets` VALUES
('GREE-IT_202605_208','Form 1: Khai báo Model phân loại chi phí bảo hành','Vương Trần','Từ chối','2026-05-29 09:49:09','Khai_Bao_Model_Bao_Hanh',NULL),
('GREE-IT_202605_398','Form 1: Phân loại chi phí bảo hành','Vương Trần','Hoàn thành','2026-05-29 07:58:41','Khai_Bao_Model_Bao_Hanh','{\"note\": \"\", \"cost_type\": \"CAC\", \"model_name\": \"GMVL-280WM/A-X(P) ODU GMVX 1 chiều\", \"product_type\": \"VRV/VRF(CAC)\", \"capacity_range\": \"10Hp - 24Hp\"}'),
('GREE-IT_202606_123','Tổng hợp vấn đề ERP (Asofr đã phản hồi)','Trần Thị Mai Thi','Mới tạo','2026-06-29 02:14:10','ERP_Yeu_Cau_Tong_Hop','{\"request_title\": \"Tổng hợp vấn đề ERP (Asofr đã phản hồi)\", \"request_detail\": \"KẾ TOÁN - Quản lý vấn đề ERP Gree & ASoft 26.06.2026.xlsx\\nLAC - CÁC VẤN ĐỀ PHÂN HỆ BÁN HÀNG_Asoft update 26062026.xlsx\\nP.KHKV - XNK PHÂN HỆ KHO & MUA HÀNG NƯỚC NGOÀI Asoft update 26062026.xlsx\\n副本HCNS - Quản lý vấn đề ERP Gree & ASoft update 26062026.xlsx\\nIssue_Admin_RAC_Asoft_update_26062026.xlsx\", \"request_category\": \"Khác\"}'),
('GREE-IT_202606_127','Seri 3K4275B010514 không gửi sms warranty được ','Hồng Phúc CS','Hoàn thành','2026-06-23 07:46:57','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"\", \"request_title\": \"Seri 3K4275B010514 không gửi sms warranty được \", \"request_detail\": \"3K4275B010514\", \"request_category\": \"Hỗ trợ khách hàng (CSKH)\"}'),
('GREE-IT_202606_142','Hỗ trợ phân quyền màn hình mới cho Admin RAC (Huỳnh Anh)','Trần Thị Mai Thi','Hoàn thành','2026-06-18 01:41:19','ERP_Yeu_Cau_Tong_Hop','{\"request_title\": \"Hỗ trợ phân quyền màn hình mới cho Admin RAC (Huỳnh Anh)\", \"request_detail\": \"CTKM > Màn hình chọn user duyệt CTKM\", \"request_category\": \"Phê duyệt / phân quyền\"}'),
('GREE-IT_202606_167','Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Mr Tưởng BH RAC','Hoàn thành','2026-06-25 03:46:58','Admin_Web_Noted_Log_Ho_Tro','{\"case_code\": \"MBHP2026060511\", \"it_assignee\": \"IT - Nam Lê\", \"evidence_link\": \"\", \"request_detail\": \" Trùng lặp Ca( cùng serial )\\nNhờ Mr Nam chuyển trạm thái ca này từ  chờ Quyết toán về trang Thái chờ Duyệt\\n=> hủy bỏ chi phí\", \"completion_date\": \"2026-06-25\", \"internal_action_log\": \"\"}'),
('GREE-IT_202606_171','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Phan Huy Hoàng','Hoàn thành','2026-06-10 07:48:08','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"linh kiện máy nén rã ra cho ca DXMUON2026060901(Đề xuất tay) ( Mã số chứng từ MNTNINH2026060195 )\", \"part_code\": \"009001060648\", \"warehouse\": \"Bình Dương - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_174','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Từ chối','2026-06-09 09:08:39','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GMVS 28KW\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_175','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Mr Thắng BH-RAC','Hoàn thành','2026-06-10 09:30:37','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Đổi dàn nóng cho ca MBBN2026060387 /DXMUON202606100004\", \"part_code\": \"BD9CN/O\", \"warehouse\": \"Hưng Yên- RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_185','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Thắng RAC','Hoàn thành','2026-06-25 07:57:26','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Đề xuất Đổi cục lạnh theo DXMUON202606250002\", \"part_code\": \" BD12HI/I \", \"warehouse\": \"Hưng Yên RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"DXMUON202606250002 /MBHP2026050839\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_191','Cập nhật thông tin trạm bảo hành BÙI CÔNG KHANH','Phan Hoàng Phong','Hoàn thành','2026-06-17 10:07:46','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Khác (Không thuộc 9 Form trên)\", \"request_title\": \"Cập nhật thông tin trạm bảo hành BÙI CÔNG KHANH\", \"request_detail\": \"Yêu cầu cập nhật thông tin Trạm Bảo Hành từ HỘ KINH DOANH BÙI CÔNG KHANH qua CÔNG TY TNHH MỘT THÀNH VIÊN KHANH TÂM GIA LAI\\n\"}'),
('GREE-IT_202606_194','Hỗ trợ khởi tạo KH là Nhân viên mới trên hệ thống ERP','Trần Thị Mai Thi','Hoàn thành','2026-06-18 01:33:04','ERP_Yeu_Cau_Tong_Hop','{\"request_title\": \"Hỗ trợ khởi tạo KH là Nhân viên mới trên hệ thống ERP\", \"request_detail\": \"Import_Excel_DanhMucDoiTuong_Update_KH là nhân viên mới tính từ Bùi Mỹ Nương trở đi\\nhttps://docs.google.com/spreadsheets/d/1_w4VlN-LGuf3YP3H8anx5JMV0Tq4LL_n/edit?usp=drive_link&ouid=100652125285106229733&rtpof=true&sd=true\", \"request_category\": \"Khởi tạo đối tượng (KH/NCC/NV)\"}'),
('GREE-IT_202606_197','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Mr Thắng BH-RAC','Hoàn thành','2026-06-09 01:39:14','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Đổi dàn nóng cho ca MBQN2026060284 /DXMUON202606080008\", \"part_code\": \"BD9CI/O\", \"warehouse\": \"Hưng Yên Tốt - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_202','Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Tưởng BH RAC','Hoàn thành','2026-06-24 08:32:37','Admin_Web_Noted_Log_Ho_Tro','{\"case_code\": \"MBBN2026050771\", \"it_assignee\": \"IT - Nam Lê\", \"evidence_link\": \"\", \"request_detail\": \"  sai chót trong vấn đề duyệt phí ( trạm đã xử lý dịch vụ => Phí không đồng)\\nNhờ Nam  đẩy lại ca này về trạm thái tạo chi phí giúp=> chuyển sang trang thái - Hoàn thành NBH\", \"completion_date\": \"2026-06-24\", \"internal_action_log\": \"\"}'),
('GREE-IT_202606_257','Import hồ sơ máy ','PHƯỢNG BH RAC','Hoàn thành','2026-06-22 03:38:24','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Form 6: Khai báo Model cho Import Hồ sơ máy\", \"request_title\": \"Import hồ sơ máy \", \"request_detail\": \"GMV-615WM/G-X\\t  Dàn nóng\\nGMV-560WM/G-X\\t  Dàn nóng\\nGMV-680WM/G-X\\t  Dàn nóng\\nGMV-ND100T/D1-T\\t  Dàn lạnh\\nGMV-ND15G/B4B-T\\t  Dàn lạnh\\n\"}'),
('GREE-IT_202606_295','Form 6: Khai báo Model cho Import Hồ sơ máy','Ms Phượng BH RAC','Hoàn thành','2026-06-09 09:09:19','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GMV-ND160T/D1-T\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_309','CA BẢO HÀNH_CHI PHÍ ĐI LẠI TÍNH 2 LẦN','Phượng BH RAC','Hoàn thành','2026-06-25 04:08:19','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Khác (Không thuộc 9 Form trên)\", \"request_title\": \"CA BẢO HÀNH_CHI PHÍ ĐI LẠI TÍNH 2 LẦN\", \"request_detail\": \"Phượng thông tin đến Nam về ca MTNA2026040578 bạn Xuân phản về lỗi phần mềm khi đóng ca. Nam xem nội dung bên dưới giúp Phượng nhé,\"}'),
('GREE-IT_202606_349','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Từ chối','2026-06-25 09:45:00','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"RF28WPd/NaA-M\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_367','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Phan Hoàng Phong','Hoàn thành','2026-06-22 10:09:17','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Tạo tồn kho lk để thay thế cho ca BH-MTQT2026060503\", \"part_code\": \"BD9CI/O\", \"warehouse\": \"Kho Hưng Yên Tốt - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_385','Sales yêu cầu mở tài khoản nội bộ','chung.ha@gree.com.vn','Hoàn thành','2026-06-29 01:33:16','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"CS-000558\", \"request_title\": \"Sales yêu cầu mở tài khoản nội bộ\", \"request_detail\": \"Họ tên khách hàng: Hà Văn Chung\\nSDT khách hàng: 84963006918\\nGree Miền Trung - khu vực Hà Tĩnh\", \"request_category\": \"Lỗi đăng nhập / Tài khoản\"}'),
('GREE-IT_202606_412','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Khoa Bảo Hành CAC','Hoàn thành','2026-06-12 06:49:35','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"linh kiện main board rã ra cho ca DXMUON2026061101(Đề xuất tay). Mã số chứng từ MTĐN2026060379\", \"part_code\": \"300027060278 \", \"warehouse\": \"Bình Dương -CAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_424','Kích hoạt BH vào PMBH cho KH Kingfood từ tháng 11 năm 2023 ','Trần Dương Nhẫn','Hoàn thành','2026-06-29 01:23:42','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Khác (Không thuộc 9 Form trên)\", \"request_title\": \"Kích hoạt BH vào PMBH cho KH Kingfood từ tháng 11 năm 2023 \", \"request_detail\": \"Nhẫn Email: Nhờ anh hỗ trợ import file kích hoạt BH vào PMBH cho KH Kingfood từ tháng 11 năm 2023 theo file đính kèm , tất cả đều được bảo hành 36 tháng toàn máy theo đề xuất bảo hành đặc biệt\"}'),
('GREE-IT_202606_425','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Phan Hoàng Phong','Hoàn thành','2026-06-03 06:55:43','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Tạo tồn kho lk để thay thế cho ca BH-MTNA2026060113\", \"part_code\": \"BD18CI/O\", \"warehouse\": \"Kho Hưng Yên Tốt - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_444','Khách C2 họ phản ánh vừa kích hoạt 10 bộ hàng BD được tính thưởng +200 gcoin/bộ, tuy nhiên vòng quay may mắn chỉ có 4 vòng.','Vũ Đạt Sale','Hoàn thành','2026-06-26 00:57:48','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"\", \"request_title\": \"Khách C2 họ phản ánh vừa kích hoạt 10 bộ hàng BD được tính thưởng +200 gcoin/bộ, tuy nhiên vòng quay may mắn chỉ có 4 vòng.\", \"request_detail\": \"3K4235B000710\\n3K48850009131\\n3K43860002806\\n3K51160001138\\n3K43860002804\\n3K51160001134\\n3K51160001167\\n3K51160001077\\n3K4275B017094\\n3K43860004126\", \"request_category\": \"Lỗi hiển thị / Dữ liệu sai\"}'),
('GREE-IT_202606_451','Giao diện của khách không có banner chương trình VQMM','Thắng Gree','Hoàn thành','2026-06-25 07:13:49','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"Zalo CS Support\", \"request_title\": \"Giao diện của khách không có banner chương trình VQMM\", \"request_detail\": \"Giao diện của khách không có banner và floating chương trình VQMM\", \"request_category\": \"Lỗi hiển thị / Dữ liệu sai\"}'),
('GREE-IT_202606_455','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Luân BH - RAC','Hoàn thành','2026-06-04 04:48:24','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Đề xuất đổi dàn lạnh cho DXMUON202606040006 Theo CS đổi mới \", \"part_code\": \"BD18CI/I\", \"warehouse\": \"Kho Bình Dương Tốt - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_466','[G-APP] Điều chỉnh giới hạn thời gian kích hoạt','Phương Huỳnh','Đang xử lý','2026-06-19 07:37:09','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"\", \"request_title\": \"[G-APP] Điều chỉnh giới hạn thời gian kích hoạt\", \"request_detail\": \"Theo nhu cầu kinh doanh, G-APP cần điều chỉnh như sau:\\n- Mở hạn thưởng T-card từ 365 ngày lên 365 x 2.\\n- Với các seri ko kích hoạt bảo hành, sau 365 x 2 kể từ ngày xuất kho cho C1, seri đó tự động được kích hoạt bảo hành với hạn 365 x 3, thông tin End User để trống để CS cập nhật sau.\", \"request_category\": \"Yêu cầu tính năng mới\"}'),
('GREE-IT_202606_489','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Phan Hoàng Phong','Hoàn thành','2026-06-16 03:57:00','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Tạo tồn kho lk để thay thế cho ca BH-MTQT2026060503\", \"part_code\": \"BD9CI/O\", \"warehouse\": \"Kho Hưng Yên Tốt - RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_514','Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Ms Giàu CS','Hoàn thành','2026-06-25 08:32:10','Admin_Web_Noted_Log_Ho_Tro','{\"case_code\": \"MNAG2026060835 \", \"it_assignee\": \"IT - Nam Lê\", \"evidence_link\": \"\", \"request_detail\": \"MNAG2026060835  \\ntrạng thái loại bảo hành => ngoài bảo hành \\nsửa lại trong bảo hành \\nVì khách đã cung cấp them serial máy còn bảo hành\", \"completion_date\": \"2026-06-25\", \"internal_action_log\": \"\"}'),
('GREE-IT_202606_526','Form 5: Đăng ký tài khoản user nội bộ Gree','Trần Đức Toàn','Hoàn thành','2026-06-02 03:37:57','Dang_Ky_Tai_Khoan_User_Noi_Bo','{\"phone\": \"0386607510\", \"full_name\": \"Trần Đức Toàn\", \"main_link\": \"https://warranty.gree.com.vn/\", \"user_group\": \"KTV Gree\", \"test_account\": {\"password\": \"123456\", \"username\": \"test\", \"test_link\": \"http://gree.baohanhso.net/\"}, \"company_email\": \"toan.tran@gree.com.vn\", \"call_center_line\": \"\"}'),
('GREE-IT_202606_535','Form 4: Đăng ký thông tin trạm bảo hành mới','Nguyễn Vũ Luân','Hoàn thành','2026-06-24 07:08:44','Dang_Ky_Tram_Bao_Hanh_Moi','{\"technicians\": [{\"name\": \"TRƯƠNG VĂN THÀ\\t0776567789\", \"phone\": \"\", \"username\": \"\"}, {\"name\": \"NGUYỄN VĂN TÍN\\t0357477489\", \"phone\": \"\", \"username\": \"\"}, {\"name\": \"TRƯƠNG VĂN GIÀU\\t0813451117\", \"phone\": \"\", \"username\": \"\"}, {\"name\": \"ĐẶNG LONG TỊNH\\t0971773303\", \"phone\": \"\", \"username\": \"\"}], \"company_info\": {\"name\": \"CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ AN UYÊN\", \"email\": \"anuyen2017@gmail.com\", \"phone\": \"0969070820\", \"tax_code\": \"0314289939\", \"bank_name\": \"MBbank\", \"tax_address\": \"B32/18 Ấp 2, Xã Hưng Long, Thành phố Hồ Chí Minh, Việt Nam\", \"bank_account\": \"7021100269007\", \"postal_address\": \"280 Khóm 8, Phường Lý Văn Lâm, Cà Mau, Việt Nam\", \"system_username\": \"anuyen-camau\", \"bank_account_name\": \"CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ AN UYÊN\"}, \"associated_warehouses\": [{\"name\": \"\", \"type\": \"Kho An Uyên - Cà Mau tốt\", \"email\": \"\"}, {\"name\": \"\", \"type\": \"Kho An Uyên - Cà Mau thu hồi\", \"email\": \"\"}]}'),
('GREE-IT_202606_560','Cập nhật chương trình VQMM trên hệ thống Gree App (start: 25/06)','Lượng MKT','Hoàn thành','2026-06-22 06:24:48','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"\", \"request_title\": \"Cập nhật chương trình VQMM trên hệ thống Gree App (start: 25/06)\", \"request_detail\": \"SCT đã phê duyệt trương trình, kế hoạch chạy chính thức 25/06/2026 (Nam và NiceSolutions thống nhất hỗ trợ cập nhật code trên server)\", \"request_category\": \"Khác\"}'),
('GREE-IT_202606_572','Hỗ trợ sale kích hoạt An Gia cho các trường hợp KH quên kích hoạt hoặc điền sai số điện thoại','Lệ Anh','Hoàn thành','2026-06-19 03:54:11','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"CS-000143, CS-000205, CS-000306\", \"request_title\": \"Hỗ trợ sale kích hoạt An Gia cho các trường hợp KH quên kích hoạt hoặc điền sai số điện thoại\", \"request_detail\": \"3K42650002011\\n3K4275B010108\\n3K42750007684\\n3K42750007995\\n3K42750007406\\n3K42750001493\\n3K4275B010168\\n3K42750001567\\n3K4275B010102\\n3K42650001733\\n3K4235B013359\\n3K42350001119\", \"request_category\": \"Hỗ trợ khách hàng (CSKH)\"}'),
('GREE-IT_202606_575','Cập nhật thời gian bảo hành 36 tháng cho dự án King Food Market','Trần Dương Nhẫn','Hoàn thành','2026-06-19 03:56:42','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Khác (Không thuộc 9 Form trên)\", \"request_title\": \"Cập nhật thời gian bảo hành 36 tháng cho dự án King Food Market\", \"request_detail\": \"Danh sách seri theo file  thuộc hàng dự án King Food Market cần ghi nhận thời gian bảo hành thành 36 tháng cho toàn máy trên hệ thống PMBH . Nhờ Anh cập nhật thông tin giúp Em lên PMBH. (file đính kèm email)\"}'),
('GREE-IT_202606_600','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:00:54','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GVC55AH-M3NTB1A/I\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_676','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:11:53','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GWC09MA-K3DNA3I/O\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 60, \"warranty_months_compressor\": 120}'),
('GREE-IT_202606_678','G-APP / Các yêu cầu hỗ trợ G-APP khác','tuan.vuong@gree.com.vn','Hoàn thành','2026-06-24 02:53:51','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"CS-000506\", \"request_title\": \"G-APP / Các yêu cầu hỗ trợ G-APP khác\", \"request_detail\": \"XNK cập nhật thiếu mã Tcard, IT vui lòng cập nhật giúp để Đại lý thực hiện KHBH. Serial: 3K42750006628, Mã Tcard: 31251380911742500313...***\", \"request_category\": \"Khác\"}'),
('GREE-IT_202606_679','Form 5: Đăng ký tài khoản user nội bộ Gree','Nguyễn Quang Tùng','Hoàn thành','2026-06-15 09:41:17','Dang_Ky_Tai_Khoan_User_Noi_Bo','{\"phone\": \"0523934214\", \"full_name\": \"Nguyễn Quang Tùng\", \"main_link\": \"https://warranty.gree.com.vn/\", \"user_group\": \"KTV Gree\", \"test_account\": {\"password\": \"123456\", \"username\": \"test\", \"test_link\": \"http://gree.baohanhso.net/\"}, \"company_email\": \"tung.nguyen@gree.com.vn\", \"call_center_line\": \"\"}'),
('GREE-IT_202606_696','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-25 09:24:11','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GMV-160WL/C-T\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_703','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:09:06','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GVC24AG-K1NNA5A/O\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_710','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:11:21','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GWC07AGA-K6DNA1A/I\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 60, \"warranty_months_compressor\": 120}'),
('GREE-IT_202606_767','Admin hỗ trợ gia hạn kích hoạt An Gia (24h)','Vương Đình Tuấn','Hoàn thành','2026-06-23 02:10:21','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"CS-000181\", \"request_title\": \"Admin hỗ trợ gia hạn kích hoạt An Gia (24h)\", \"request_detail\": \"Serial: 3K4235B004855\", \"request_category\": \"Hỗ trợ khách hàng (CSKH)\"}'),
('GREE-IT_202606_776','G-APP / Tài khoản nội bộ','hiep.huynh@gmail.com','Hoàn thành','2026-06-24 02:56:26','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"CS-000513\", \"request_title\": \"G-APP / Tài khoản nội bộ\", \"request_detail\": \"SDT đăng ký TK G-APP: 84906119383\\nTên cá nhân / doanh nghiệp đăng ký TK G-APP: Nguyễn Toàn Thắng\\n\", \"request_category\": \"Lỗi đăng nhập / Tài khoản\"}'),
('GREE-IT_202606_783','Form 6: Khai báo Model cho Import Hồ sơ máy','Ms Phượng BH RAC','Hoàn thành','2026-06-09 09:00:01','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GMVL-504WM/A-X(P)\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_791','Form 6: Khai báo Model cho Import Hồ sơ máy','Phượng BH RAC','Hoàn thành','2026-06-19 08:10:45','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GMV-160WL/C1-S\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_806','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:09:30','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GVC48AL-M6NNC7A/I \", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_832','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Từ chối','2026-06-25 09:43:52','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GWC09PB-K3D0P4/I\", \"machine_type\": \"Dàn lạnh\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_845','Form 1: Khai báo Model phân loại chi phí bảo hành','Vương CAC','Từ chối','2026-06-01 04:20:14','Khai_Bao_Model_Bao_Hanh','{\"note\": \"\", \"cost_type\": \"CAC\", \"model_name\": \"\", \"product_type\": \"BĐT - Bếp điện từ\", \"capacity_range\": \"9.000 - 18.000 Btu\"}'),
('GREE-IT_202606_854','Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)','Tuong BH RAC','Hoàn thành','2026-06-24 02:39:07','Admin_Web_Noted_Log_Ho_Tro','{\"case_code\": \"MBPT2026050737 MBBN2026050661\", \"it_assignee\": \"IT - Nam Lê\", \"evidence_link\": \"\", \"request_detail\": \" sai nội dung chi phí đi lại ( 2 lần )\\nNhờ em điều chỉnh chi phí đi lại của 2 chứng từ trên về 01 lần , cho đúng với thực tế\", \"completion_date\": \"2026-06-24\", \"internal_action_log\": \"\"}'),
('GREE-IT_202606_858','Form 3: Yêu cầu điều chỉnh tồn kho hệ thống','Thắng RAC','Hoàn thành','2026-06-12 04:31:24','Yeu_Cau_Dieu_Chinh_Ton_Kho','{\"note\": \"Đề xuất Đổi cục nóng cho Khách hàng theo ĐX hỗ trợ của sale\", \"part_code\": \"[BD9CN/O] Outdoor\", \"warehouse\": \"Hưng Yên RAC\", \"part_nature\": \"Linh kiện mượn\", \"export_voucher\": \"MBLCAI2026060419/DXMUON202606120005\", \"adjusted_quantity\": 1, \"evidence_image_url\": \"\"}'),
('GREE-IT_202606_868','Tin nhắn chưa có ra khỏi hệ thống để đẩy qua bên NCC','Phạm Văn Tâm','Hoàn thành','2026-06-18 01:35:44','GreeApp_Yeu_Cau_Tong_Hop','{\"original_ref\": \"[CS-000468] Gree CS Ticket\", \"request_title\": \"Tin nhắn chưa có ra khỏi hệ thống để đẩy qua bên NCC\", \"request_detail\": \"Ngày 08/06/2026 tk Phạm Văn Tâm có kích hoạt 18 bộ cho khách hàng Chú Mạnh sdt 84969235259 - Tuy nhiên khách hàng phản hồi không nhận được SMS từ Gree xác nhận việc đã được kích hoạt bảo hành => Khách hàng Phạm Văn Tâm không thu được tiền máy và chi phí lắp đặt\", \"request_category\": \"Lỗi đăng nhập / Tài khoản\"}'),
('GREE-IT_202606_881','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:13:35','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GWC12AAB-K6DNA1B/O\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 60, \"warranty_months_compressor\": 120}'),
('GREE-IT_202606_942','Form 5: Đăng ký tài khoản user nội bộ Gree','Mr Hổ BH-RAC','Hoàn thành','2026-06-01 02:35:11','Dang_Ky_Tai_Khoan_User_Noi_Bo','{\"phone\": \"test\", \"full_name\": \"test\", \"main_link\": \"https://warranty.gree.com.vn/\", \"user_group\": \"KTV Gree\", \"test_account\": {\"password\": \"123456\", \"username\": \"test\", \"test_link\": \"http://gree.baohanhso.net/\"}, \"company_email\": \"test@gree.com.vn\", \"call_center_line\": \"\"}'),
('GREE-IT_202606_948','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-25 09:43:20','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"G-8WDXY/G-M\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_949','Hỗ trợ khởi tạo Model cho Import Hồ sơ máy','Phượng BH RAC','Hoàn thành','2026-06-22 09:47:06','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Form 6: Khai báo Model cho Import Hồ sơ máy\", \"request_title\": \"Hỗ trợ khởi tạo Model cho Import Hồ sơ máy\", \"request_detail\": \"--\\nGMV-ND71PMS/A1-T\\tdàn lạnh\\nGMV-ND80PMS/A1-T\\tdàn lạnh\\nGMV-ND100PMS/A1-T\\tdàn lạnh\\nGMV-ND90PMS/A1-T\\tdàn lạnh\\nGMV-ND18PLS/C1-T\\tdàn lạnh\\n- Thời hạn Bảo hành 24 - 36\"}'),
('GREE-IT_202606_967','Form 6: Khai báo Model cho Import Hồ sơ máy','Vũ XNK','Hoàn thành','2026-06-09 09:10:08','Khai_Bao_Model_Ho_So_May','{\"model_name\": \"GVC48AL-M6NNC7A/O\", \"machine_type\": \"Dàn nóng\", \"warranty_months_machine\": 24, \"warranty_months_compressor\": 36}'),
('GREE-IT_202606_988','Định dạng theo format dd/mm/yyyy h:mm:ss ','Dương Chiếu Quốc','Mới tạo','2026-06-29 07:54:00','Yeu_Cau_Tong_Hop_Khac','{\"related_form\": \"Form 1: Khai báo Model phân loại chi phí bảo hành\", \"request_title\": \"Định dạng theo format dd/mm/yyyy h:mm:ss \", \"request_detail\": \"KPI mới áp dụng cho Bộ phận CS hiện tại đang có 1 chỉ tiêu Tốc độ Happy Call với công thức tính toán như sau:\\nTốc độ 1 ca Happy Call = Ngày CSKH hoàn thành (1) – Ngày TBH hoàn thành (2)\\nHiện tại (1) & (2) trong Báo cáo “Thống kê khảo sát chi tiết” vẫn định dạng theo format dd/mm/yyyy, đang chưa đúng.\\n\\nNam hỗ trợ chỉnh lại dữ liệu 2 cột (1) & (2) nêu trên định dạng theo format dd/mm/yyyy h:mm:ss để triển khai tính toán đúng.\\n\"}');
/*!40000 ALTER TABLE `tickets` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-29 16:40:09
