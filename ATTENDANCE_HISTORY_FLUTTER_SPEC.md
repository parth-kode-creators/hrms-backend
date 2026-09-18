# HRMS Mobile — Super Admin Check-In History (Flutter Implementation Guide)

This guide documents the full Flutter implementation required for **Super Admins** (and **HR Admins**) to view company-wide check-in / attendance history with date filters, status filters, employee search, and pagination.

---

## 1. Backend API Specification

### Endpoint Details
- **Method**: `GET`
- **Path**: `/api/v1/attendance/history` (also available as `/attendance/history`)
- **Authentication**: `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Allowed Roles**: `super_admin`, `hr_admin` (non-admins receive `403 Forbidden`)

### Query Parameters
| Parameter | Type | Required | Default | Description | Example |
|---|---|---|---|---|---|
| `date` | `String` | No | `null` | Exact date (`YYYY-MM-DD`) | `2026-09-18` |
| `start_date` | `String` | No | `null` | Start date for range filter | `2026-09-01` |
| `end_date` | `String` | No | `null` | End date for range filter | `2026-09-18` |
| `employee_id` | `int` | No | `null` | Filter by specific employee ID | `4` |
| `department_id` | `int` | No | `null` | Filter by department ID | `2` |
| `status` | `String` | No | `null` | Filter by attendance status | `present`, `wfh_pending_approval` |
| `page` | `int` | No | `1` | Page number (1-based) | `1` |
| `limit` | `int` | No | `20` | Records per page (1-100) | `20` |

### Sample Response (`200 OK`)
```json
{
  "total": 45,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": 102,
      "employee_id": 5,
      "employee_name": "Jane Doe",
      "employee_code": "EMP0005",
      "department": "Engineering",
      "date": "2026-09-18",
      "check_in_time": "2026-09-18T09:12:45+00:00",
      "check_out_time": "2026-09-18T18:05:10+00:00",
      "check_in_method": "mobile_geofence",
      "check_out_method": "mobile_geofence",
      "check_in_ip": "192.168.1.104",
      "check_in_lat": 22.307159,
      "check_in_lng": 73.181219,
      "status": "present",
      "is_regularized": false,
      "regularize_reason": null,
      "total_hours": 8.87,
      "created_at": "2026-09-18T09:12:45+00:00"
    }
  ]
}
```

---

## 2. File Changes Checklist for Flutter

| File Path | Action | Description |
|---|---|---|
| `lib/models/attendance_history.dart` | **Create** | Data models `AttendanceHistoryItem` & `AttendanceHistoryResponse` |
| `lib/services/attendance_service.dart` | **Create / Update** | Add `getAttendanceHistory()` API call |
| `lib/providers/attendance_provider.dart` | **Create / Update** | State management for history, filters, and pagination |
| `lib/screens/admin/admin_attendance_history_screen.dart` | **Create** | Screen with date filter chips, date picker, stats, and check-in cards |
| `lib/screens/dashboard/dashboard_screen.dart` | **Update** | Add "Attendance History" navigation card for Super Admin |
| `lib/router/app_router.dart` | **Update** | Register `/admin/attendance-history` route |

---

## 3. Implementation Code

### 3.1 Model: `lib/models/attendance_history.dart`

```dart
class AttendanceHistoryResponse {
  final int total;
  final int page;
  final int limit;
  final List<AttendanceHistoryItem> items;

  AttendanceHistoryResponse({
    required this.total,
    required this.page,
    required this.limit,
    required this.items,
  });

  factory AttendanceHistoryResponse.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List? ?? [];
    return AttendanceHistoryResponse(
      total: json['total'] ?? 0,
      page: json['page'] ?? 1,
      limit: json['limit'] ?? 20,
      items: list.map((e) => AttendanceHistoryItem.fromJson(e)).toList(),
    );
  }
}

class AttendanceHistoryItem {
  final int id;
  final int employeeId;
  final String employeeName;
  final String employeeCode;
  final String? department;
  final String date; // YYYY-MM-DD
  final DateTime? checkInTime;
  final DateTime? checkOutTime;
  final String? checkInMethod;
  final String? checkOutMethod;
  final String? checkInIp;
  final double? checkInLat;
  final double? checkInLng;
  final String status;
  final bool isRegularized;
  final String? regularizeReason;
  final double? totalHours;
  final DateTime? createdAt;

  AttendanceHistoryItem({
    required this.id,
    required this.employeeId,
    required this.employeeName,
    required this.employeeCode,
    this.department,
    required this.date,
    this.checkInTime,
    this.checkOutTime,
    this.checkInMethod,
    this.checkOutMethod,
    this.checkInIp,
    this.checkInLat,
    this.checkInLng,
    required this.status,
    this.isRegularized = false,
    this.regularizeReason,
    this.totalHours,
    this.createdAt,
  });

  factory AttendanceHistoryItem.fromJson(Map<String, dynamic> json) {
    DateTime? parseDt(dynamic val) {
      if (val == null) return null;
      return DateTime.tryParse(val.toString())?.toLocal();
    }

    double? parseDouble(dynamic val) {
      if (val == null) return null;
      return double.tryParse(val.toString());
    }

    return AttendanceHistoryItem(
      id: json['id'],
      employeeId: json['employee_id'],
      employeeName: json['employee_name'] ?? 'Unknown Employee',
      employeeCode: json['employee_code'] ?? '—',
      department: json['department'],
      date: json['date'] ?? '',
      checkInTime: parseDt(json['check_in_time']),
      checkOutTime: parseDt(json['check_out_time']),
      checkInMethod: json['check_in_method'],
      checkOutMethod: json['check_out_method'],
      checkInIp: json['check_in_ip'],
      checkInLat: parseDouble(json['check_in_lat']),
      checkInLng: parseDouble(json['check_in_lng']),
      status: json['status'] ?? 'present',
      isRegularized: json['is_regularized'] ?? false,
      regularizeReason: json['regularize_reason'],
      totalHours: parseDouble(json['total_hours']),
      createdAt: parseDt(json['created_at']),
    );
  }
}
```

---

### 3.2 Service Layer: `lib/services/attendance_service.dart`

Add this method to `AttendanceService`:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/attendance_history.dart';

class AttendanceService {
  final String baseUrl;
  final String token;

  AttendanceService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $token',
  };

  /// Fetch company-wide attendance history for Super Admin & HR
  Future<AttendanceHistoryResponse> getAttendanceHistory({
    String? date,
    String? startDate,
    String? endDate,
    int? employeeId,
    int? departmentId,
    String? status,
    int page = 1,
    int limit = 20,
  }) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'limit': limit.toString(),
    };

    if (date != null && date.isNotEmpty) {
      queryParams['date'] = date;
    } else {
      if (startDate != null && startDate.isNotEmpty) queryParams['start_date'] = startDate;
      if (endDate != null && endDate.isNotEmpty) queryParams['end_date'] = endDate;
    }

    if (employeeId != null) queryParams['employee_id'] = employeeId.toString();
    if (departmentId != null) queryParams['department_id'] = departmentId.toString();
    if (status != null && status.isNotEmpty) queryParams['status'] = status;

    final uri = Uri.parse('$baseUrl/attendance/history').replace(queryParameters: queryParams);
    final response = await http.get(uri, headers: _headers);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return AttendanceHistoryResponse.fromJson(data);
    } else if (response.statusCode == 403) {
      throw Exception('Access denied: Super Admin or HR Admin role required');
    } else {
      final error = jsonDecode(response.body);
      throw Exception(error['detail'] ?? 'Failed to load attendance history');
    }
  }
}
```

---

### 3.3 Provider: `lib/providers/attendance_provider.dart`

Add state management for the check-in history screen:

```dart
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/attendance_history.dart';
import '../services/attendance_service.dart';

class AttendanceProvider extends ChangeNotifier {
  final AttendanceService attendanceService;

  AttendanceProvider({required this.attendanceService});

  // State
  List<AttendanceHistoryItem> _items = [];
  int _total = 0;
  int _currentPage = 1;
  final int _limit = 20;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  String? _errorMessage;

  // Active Filters
  DateTime? _selectedDate;
  DateTimeRange? _selectedDateRange;
  int? _selectedEmployeeId;
  String? _selectedStatus;

  // Getters
  List<AttendanceHistoryItem> get items => _items;
  int get total => _total;
  int get currentPage => _currentPage;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _items.length < _total;
  String? get errorMessage => _errorMessage;
  DateTime? get selectedDate => _selectedDate;
  DateTimeRange? get selectedDateRange => _selectedDateRange;
  int? get selectedEmployeeId => _selectedEmployeeId;
  String? get selectedStatus => _selectedStatus;

  final DateFormat _apiDateFormat = DateFormat('yyyy-MM-dd');

  /// Initial load or pull-to-refresh
  Future<void> fetchHistory({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 1;
      _items = [];
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      String? dateParam;
      String? startParam;
      String? endParam;

      if (_selectedDate != null) {
        dateParam = _apiDateFormat.format(_selectedDate!);
      } else if (_selectedDateRange != null) {
        startParam = _apiDateFormat.format(_selectedDateRange!.start);
        endParam = _apiDateFormat.format(_selectedDateRange!.end);
      }

      final response = await attendanceService.getAttendanceHistory(
        date: dateParam,
        startDate: startParam,
        endDate: endParam,
        employeeId: _selectedEmployeeId,
        status: _selectedStatus,
        page: _currentPage,
        limit: _limit,
      );

      _items = response.items;
      _total = response.total;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Load next page for pagination
  Future<void> loadMore() async {
    if (_isLoading || _isLoadingMore || !hasMore) return;

    _isLoadingMore = true;
    notifyListeners();

    try {
      String? dateParam;
      String? startParam;
      String? endParam;

      if (_selectedDate != null) {
        dateParam = _apiDateFormat.format(_selectedDate!);
      } else if (_selectedDateRange != null) {
        startParam = _apiDateFormat.format(_selectedDateRange!.start);
        endParam = _apiDateFormat.format(_selectedDateRange!.end);
      }

      final nextPage = _currentPage + 1;
      final response = await attendanceService.getAttendanceHistory(
        date: dateParam,
        startDate: startParam,
        endDate: endParam,
        employeeId: _selectedEmployeeId,
        status: _selectedStatus,
        page: nextPage,
        limit: _limit,
      );

      _items.addAll(response.items);
      _currentPage = nextPage;
      _total = response.total;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  /// Set single date filter (e.g. today or yesterday)
  void setSingleDateFilter(DateTime? date) {
    _selectedDate = date;
    _selectedDateRange = null;
    fetchHistory(refresh: true);
  }

  /// Set date range filter
  void setDateRangeFilter(DateTimeRange? range) {
    _selectedDateRange = range;
    _selectedDate = null;
    fetchHistory(refresh: true);
  }

  /// Filter by employee ID
  void setEmployeeFilter(int? employeeId) {
    _selectedEmployeeId = employeeId;
    fetchHistory(refresh: true);
  }

  /// Filter by status (e.g. 'present', 'wfh_pending_approval')
  void setStatusFilter(String? status) {
    _selectedStatus = status;
    fetchHistory(refresh: true);
  }

  /// Clear all filters and reload
  void clearAllFilters() {
    _selectedDate = null;
    _selectedDateRange = null;
    _selectedEmployeeId = null;
    _selectedStatus = null;
    fetchHistory(refresh: true);
  }
}
```

---

### 3.4 Screen: `lib/screens/admin/admin_attendance_history_screen.dart`

Complete screen implementation with quick filter chips, date range picker, statistics summary, and check-in item details:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../providers/attendance_provider.dart';
import '../../models/attendance_history.dart';

class AdminAttendanceHistoryScreen extends StatefulWidget {
  const AdminAttendanceHistoryScreen({Key? key}) : super(key: key);

  @override
  State<AdminAttendanceHistoryScreen> createState() => _AdminAttendanceHistoryScreenState();
}

class _AdminAttendanceHistoryScreenState extends State<AdminAttendanceHistoryScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // By default show today's attendance
      final provider = context.read<AttendanceProvider>();
      provider.setSingleDateFilter(DateTime.now());
    });

    _scrollController.addListener(() {
      if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
        context.read<AttendanceProvider>().loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _pickDate(BuildContext context) async {
    final provider = context.read<AttendanceProvider>();
    final picked = await showDatePicker(
      context: context,
      initialDate: provider.selectedDate ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime(2030),
    );
    if (picked != null) {
      provider.setSingleDateFilter(picked);
    }
  }

  Future<void> _pickDateRange(BuildContext context) async {
    final provider = context.read<AttendanceProvider>();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2030),
      initialDateRange: provider.selectedDateRange ??
          DateTimeRange(
            start: DateTime.now().subtract(const Duration(days: 7)),
            end: DateTime.now(),
          ),
    );
    if (picked != null) {
      provider.setDateRangeFilter(picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<AttendanceProvider>();
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Check-In History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.calendar_today_outlined),
            tooltip: 'Pick Single Date',
            onPressed: () => _pickDate(context),
          ),
          IconButton(
            icon: const Icon(Icons.date_range_outlined),
            tooltip: 'Pick Date Range',
            onPressed: () => _pickDateRange(context),
          ),
          if (provider.selectedDate != null || provider.selectedDateRange != null || provider.selectedStatus != null)
            IconButton(
              icon: const Icon(Icons.filter_alt_off_outlined),
              tooltip: 'Clear Filters',
              onPressed: () => provider.clearAllFilters(),
            ),
        ],
      ),
      body: Column(
        children: [
          // Filter Chips Row
          _buildFilterChips(context, provider),

          // Active filter banner
          _buildActiveFilterInfo(context, provider),

          // Content
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => provider.fetchHistory(refresh: true),
              child: provider.isLoading && provider.items.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : provider.errorMessage != null && provider.items.isEmpty
                      ? _buildErrorView(provider)
                      : provider.items.isEmpty
                          ? _buildEmptyView()
                          : _buildListView(provider),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChips(BuildContext context, AttendanceProvider provider) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    bool isTodaySelected = provider.selectedDate != null &&
        provider.selectedDate!.year == today.year &&
        provider.selectedDate!.month == today.month &&
        provider.selectedDate!.day == today.day;

    bool isYesterdaySelected = provider.selectedDate != null &&
        provider.selectedDate!.year == yesterday.year &&
        provider.selectedDate!.month == yesterday.month &&
        provider.selectedDate!.day == yesterday.day;

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          ChoiceChip(
            label: const Text('Today'),
            selected: isTodaySelected,
            onSelected: (_) => provider.setSingleDateFilter(today),
          ),
          const SizedBox(width: 8),
          ChoiceChip(
            label: const Text('Yesterday'),
            selected: isYesterdaySelected,
            onSelected: (_) => provider.setSingleDateFilter(yesterday),
          ),
          const SizedBox(width: 8),
          ChoiceChip(
            label: const Text('All Time'),
            selected: provider.selectedDate == null && provider.selectedDateRange == null,
            onSelected: (_) => provider.setSingleDateFilter(null),
          ),
          const SizedBox(width: 8),
          ActionChip(
            avatar: const Icon(Icons.date_range, size: 16),
            label: Text(provider.selectedDateRange != null
                ? '${DateFormat('MM/dd').format(provider.selectedDateRange!.start)} - ${DateFormat('MM/dd').format(provider.selectedDateRange!.end)}'
                : 'Custom Range'),
            onPressed: () => _pickDateRange(context),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveFilterInfo(BuildContext context, AttendanceProvider provider) {
    String label = 'Showing: All Records';
    if (provider.selectedDate != null) {
      label = 'Date: ${DateFormat('EEE, MMM d, yyyy').format(provider.selectedDate!)}';
    } else if (provider.selectedDateRange != null) {
      label = 'Range: ${DateFormat('MMM d').format(provider.selectedDateRange!.start)} – ${DateFormat('MMM d, yyyy').format(provider.selectedDateRange!.end)}';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.4),
      child: Row(
        children: [
          Icon(Icons.info_outline, size: 16, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
          Text(
            '${provider.total} records',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildListView(AttendanceProvider provider) {
    return ListView.separated(
      controller: _scrollController,
      padding: const EdgeInsets.all(12),
      itemCount: provider.items.length + (provider.isLoadingMore ? 1 : 0),
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        if (index == provider.items.length) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(16.0),
              child: CircularProgressIndicator(),
            ),
          );
        }

        final item = provider.items[index];
        return _buildAttendanceCard(context, item);
      },
    );
  }

  Widget _buildAttendanceCard(BuildContext context, AttendanceHistoryItem item) {
    final theme = Theme.of(context);
    final isPresent = item.status.toLowerCase() == 'present';
    final timeFormat = DateFormat('hh:mm a');

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _showDetailsSheet(context, item),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header: Employee details & Status Badge
              Row(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: theme.colorScheme.primaryContainer,
                    child: Text(
                      item.employeeName.isNotEmpty ? item.employeeName[0].toUpperCase() : '?',
                      style: TextStyle(fontWeight: FontWeight.bold, color: theme.colorScheme.onPrimaryContainer),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.employeeName,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                        ),
                        Text(
                          '${item.employeeCode} • ${item.department ?? "General"}',
                          style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  _buildStatusChip(item.status),
                ],
              ),
              const Divider(height: 20),

              // Timestamps Row
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Check In
                  Row(
                    children: [
                      const Icon(Icons.login, size: 18, color: Colors.green),
                      const SizedBox(width: 6),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Check In', style: TextStyle(fontSize: 11, color: Colors.grey)),
                          Text(
                            item.checkInTime != null ? timeFormat.format(item.checkInTime!) : '—',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                          ),
                        ],
                      ),
                    ],
                  ),

                  // Check Out
                  Row(
                    children: [
                      const Icon(Icons.logout, size: 18, color: Colors.orange),
                      const SizedBox(width: 6),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Check Out', style: TextStyle(fontSize: 11, color: Colors.grey)),
                          Text(
                            item.checkOutTime != null ? timeFormat.format(item.checkOutTime!) : '—',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                          ),
                        ],
                      ),
                    ],
                  ),

                  // Total Hours
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      const Text('Total Hours', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      Text(
                        item.totalHours != null ? '${item.totalHours!.toStringAsFixed(1)} hrs' : '—',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                          color: (item.totalHours ?? 0) >= 8 ? Colors.green : Colors.grey.shade800,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusChip(String status) {
    Color bg = Colors.green.shade50;
    Color fg = Colors.green.shade800;

    if (status.contains('wfh')) {
      bg = Colors.blue.shade50;
      fg = Colors.blue.shade800;
    } else if (status.contains('absent') || status.contains('rejected')) {
      bg = Colors.red.shade50;
      fg = Colors.red.shade800;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }

  void _showDetailsSheet(BuildContext context, AttendanceHistoryItem item) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Attendance Details — ${item.employeeName}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              const SizedBox(height: 12),
              _buildDetailRow('Date', item.date),
              _buildDetailRow('Method', item.checkInMethod ?? '—'),
              _buildDetailRow('IP Address', item.checkInIp ?? '—'),
              if (item.checkInLat != null && item.checkInLng != null)
                _buildDetailRow('Coordinates', '${item.checkInLat}, ${item.checkInLng}'),
              if (item.isRegularized)
                _buildDetailRow('Regularized', 'Yes (${item.regularizeReason ?? "No note"})'),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildEmptyView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.event_busy, size: 64, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          const Text(
            'No check-in records found',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 6),
          Text(
            'Try adjusting your date or status filters.',
            style: TextStyle(color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView(AttendanceProvider provider) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 12),
            Text(
              provider.errorMessage ?? 'Something went wrong',
              textAlign: TextAlign.center,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => provider.fetchHistory(refresh: true),
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

### 3.5 Integration into Dashboard: `lib/screens/dashboard/dashboard_screen.dart`

Add a Quick Action card or Admin menu tile inside `dashboard_screen.dart` for users with role `super_admin` or `hr_admin`:

```dart
// Check if user is Super Admin or HR Admin
final isSuperAdmin = currentUser.role == 'super_admin';
final isHrAdmin = currentUser.role == 'hr_admin';

if (isSuperAdmin || isHrAdmin)
  Card(
    elevation: 2,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    child: ListTile(
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.indigo.shade50,
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Icon(Icons.access_time_filled, color: Colors.indigo),
      ),
      title: const Text('Check-In History', style: TextStyle(fontWeight: FontWeight.bold)),
      subtitle: const Text('Company-wide employee attendance & dates'),
      trailing: const Icon(Icons.arrow_forward_ios, size: 16),
      onTap: () {
        Navigator.pushNamed(context, '/admin/attendance-history');
      },
    ),
  ),
```

---

### 3.6 Router Registration: `lib/router/app_router.dart`

Register the route in your app's router:

```dart
case '/admin/attendance-history':
  return MaterialPageRoute(
    builder: (_) => const AdminAttendanceHistoryScreen(),
  );
```

---

## 4. Testing & Verification Checklist

1. **Date Filter**: Select "Today", "Yesterday", and a custom date via Date Picker. Verify only records for that date appear.
2. **Date Range Filter**: Open the date range dialog, select a week, and ensure all attendance records within the range load.
3. **Pagination**: Scroll past the initial 20 records to verify infinite scroll fetches the next batch.
4. **Security**: Log in with an `employee` account and verify that attempting to access the endpoint returns `403 Forbidden` and displays the proper access denied message.
