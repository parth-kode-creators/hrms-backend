# HRMS Mobile — Employee Management (System Admin & HR)
## Architecture, API Endpoints & Flutter Implementation Guide

This specification covers the full Employee Management module for **System Administrators** (`super_admin`) and **HR Administrators** (`hr_admin`) in the Flutter mobile application.

---

## 1. Backend API Endpoints Reference

**Base URL**: `https://hrms-backend-z5vv.onrender.com` (Production) or `http://10.0.2.2:8000` (Android Emulator)

All endpoints require:
`Authorization: Bearer <JWT_ACCESS_TOKEN>`

| Action | Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|---|
| **List Employees** | `GET` | `/employees` | `super_admin`, `hr_admin`, `manager` | Paginated employee list with search and filters |
| **Get Employee Details** | `GET` | `/employees/{id}` | `super_admin`, `hr_admin`, `manager` | Full employee profile with relations |
| **Create Employee** | `POST` | `/employees` | `super_admin`, `hr_admin` | Adds employee, auto-generates `employee_code`, user login & leave balances |
| **Update Employee** | `PUT` | `/employees/{id}` | `super_admin`, `hr_admin` | Modifies employee profile, department, designation, status |
| **Deactivate / Delete** | `DELETE` | `/employees/{id}` | `super_admin`, `hr_admin` | Soft-deactivates account (or `?hard_delete=true` for permanent purge) |
| **Get Departments** | `GET` | `/departments` | All authenticated users | Fetches list of departments for dropdowns |
| **Get Office Locations** | `GET` | `/office-locations` | All authenticated users | Fetches registered office locations for dropdowns |

---

### Request & Response Payloads

#### 1.1 `GET /employees`
**Query Parameters**:
- `page` (default: 1)
- `limit` (default: 20)
- `department_id` (optional `int`)
- `status` (optional `string`, e.g. `"active"`, `"inactive"`)

**Response (`200 OK`)**:
```json
{
  "total": 45,
  "page": 1,
  "items": [
    {
      "id": 1,
      "full_name": "System Administrator",
      "designation": "System Administrator / HR Director",
      "department": "Human Resources",
      "status": "active"
    }
  ]
}
```

---

#### 1.2 `POST /employees`
**Request Body**:
```json
{
  "full_name": "John Doe",
  "email": "john.doe@company.com",
  "phone": "+91 9876543210",
  "department_id": 2,
  "designation": "Senior Flutter Developer",
  "date_of_joining": "2026-09-18",
  "office_location_id": 1,
  "role": "employee",
  "password": "DefaultPassword123!"
}
```
*Roles available: `"employee"`, `"manager"`, `"hr_admin"`, `"super_admin"`.*

**Response (`201 Created`)**:
```json
{
  "id": 2,
  "employee_code": "EMP0002",
  "full_name": "John Doe",
  "email": "john.doe@company.com",
  "status": "active",
  "designation": "Senior Flutter Developer",
  "department": { "id": 2, "name": "Engineering" },
  "office_location": { "id": 1, "name": "Head Office" }
}
```

---

#### 1.3 `PUT /employees/{id}`
**Request Body** *(all fields optional, send only changed fields)*:
```json
{
  "full_name": "John Doe",
  "phone": "+91 9876543211",
  "department_id": 2,
  "designation": "Lead Flutter Engineer",
  "office_location_id": 1,
  "status": "active"
}
```

**Response (`200 OK`)**: Updated `EmployeeDetail` object.

---

#### 1.4 `DELETE /employees/{id}`
**Query Parameters**:
- `hard_delete` (`false` by default)
  - `false`: Sets employee status to `"inactive"` and disables login.
  - `true`: Permanently purges record.

**Response (`200 OK`)**:
```json
{
  "status": "success",
  "message": "Employee John Doe deactivated successfully"
}
```

---

## 2. Dart Models (`lib/models/employee.dart`)

```dart
class EmployeeListItem {
  final int id;
  final String fullName;
  final String? designation;
  final String? department;
  final String status;

  EmployeeListItem({
    required this.id,
    required this.fullName,
    this.designation,
    this.department,
    required this.status,
  });

  factory EmployeeListItem.fromJson(Map<String, dynamic> json) {
    return EmployeeListItem(
      id: json['id'],
      fullName: json['full_name'] ?? '',
      designation: json['designation'],
      department: json['department'],
      status: json['status'] ?? 'active',
    );
  }
}

class EmployeeDetail {
  final int id;
  final String employeeCode;
  final String fullName;
  final String email;
  final String? phone;
  final String? designation;
  final String? status;
  final int? departmentId;
  final String? departmentName;
  final int? officeLocationId;
  final String? officeLocationName;
  final String? dateOfJoining;

  EmployeeDetail({
    required this.id,
    required this.employeeCode,
    required this.fullName,
    required this.email,
    this.phone,
    this.designation,
    this.status,
    this.departmentId,
    this.departmentName,
    this.officeLocationId,
    this.officeLocationName,
    this.dateOfJoining,
  });

  factory EmployeeDetail.fromJson(Map<String, dynamic> json) {
    return EmployeeDetail(
      id: json['id'],
      employeeCode: json['employee_code'] ?? '',
      fullName: json['full_name'] ?? '',
      email: json['email'] ?? '',
      phone: json['phone'],
      designation: json['designation'],
      status: json['status'] ?? 'active',
      departmentId: json['department'] != null ? json['department']['id'] : null,
      departmentName: json['department'] != null ? json['department']['name'] : null,
      officeLocationId: json['office_location'] != null ? json['office_location']['id'] : null,
      officeLocationName: json['office_location'] != null ? json['office_location']['name'] : null,
      dateOfJoining: json['date_of_joining'],
    );
  }
}
```

---

## 3. Flutter API Service Layer (`lib/services/employee_service.dart`)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/employee.dart';

class EmployeeService {
  final String baseUrl;
  final String token;

  EmployeeService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $token',
  };

  // 1. Fetch Paginated Employees
  Future<List<EmployeeListItem>> getEmployees({int page = 1, int limit = 50, String? status}) async {
    String url = '$baseUrl/employees?page=$page&limit=$limit';
    if (status != null) url += '&status=$status';

    final response = await http.get(Uri.parse(url), headers: _headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final List items = data['items'] ?? [];
      return items.map((e) => EmployeeListItem.fromJson(e)).toList();
    }
    throw Exception('Failed to load employees (${response.statusCode})');
  }

  // 2. Fetch Single Employee
  Future<EmployeeDetail> getEmployeeById(int id) async {
    final response = await http.get(Uri.parse('$baseUrl/employees/$id'), headers: _headers);
    if (response.statusCode == 200) {
      return EmployeeDetail.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load employee details');
  }

  // 3. Create Employee
  Future<EmployeeDetail> createEmployee(Map<String, dynamic> payload) async {
    final response = await http.post(
      Uri.parse('$baseUrl/employees'),
      headers: _headers,
      body: jsonEncode(payload),
    );
    if (response.statusCode == 201) {
      return EmployeeDetail.fromJson(jsonDecode(response.body));
    }
    final error = jsonDecode(response.body);
    throw Exception(error['detail'] ?? 'Failed to create employee');
  }

  // 4. Update Employee
  Future<EmployeeDetail> updateEmployee(int id, Map<String, dynamic> payload) async {
    final response = await http.put(
      Uri.parse('$baseUrl/employees/$id'),
      headers: _headers,
      body: jsonEncode(payload),
    );
    if (response.statusCode == 200) {
      return EmployeeDetail.fromJson(jsonDecode(response.body));
    }
    final error = jsonDecode(response.body);
    throw Exception(error['detail'] ?? 'Failed to update employee');
  }

  // 5. Deactivate / Delete Employee
  Future<void> deleteEmployee(int id, {bool hardDelete = false}) async {
    final response = await http.delete(
      Uri.parse('$baseUrl/employees/$id?hard_delete=$hardDelete'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      final error = jsonDecode(response.body);
      throw Exception(error['detail'] ?? 'Failed to delete employee');
    }
  }

  // 6. Lookup helpers
  Future<List<Map<String, dynamic>>> getDepartments() async {
    final res = await http.get(Uri.parse('$baseUrl/departments'), headers: _headers);
    return res.statusCode == 200 ? List<Map<String, dynamic>>.from(jsonDecode(res.body)) : [];
  }

  Future<List<Map<String, dynamic>>> getOfficeLocations() async {
    final res = await http.get(Uri.parse('$baseUrl/office-locations'), headers: _headers);
    return res.statusCode == 200 ? List<Map<String, dynamic>>.from(jsonDecode(res.body)) : [];
  }
}
```

---

## 4. Flutter Screens

### Screen 1: Employee List Screen (`lib/screens/admin/employee_list_screen.dart`)
* Features:
  - Search filter by name / designation.
  - Pull-to-refresh.
  - Status badge (`active` green, `inactive` grey).
  - Floating Action Button to **Add Employee**.
  - Tap card to **Edit**.
  - Swipe or menu to **Deactivate / Delete**.

```dart
import 'package:flutter/material.dart';
import '../../models/employee.dart';
import '../../services/employee_service.dart';
import 'add_employee_screen.dart';
import 'edit_employee_screen.dart';

class EmployeeListScreen extends StatefulWidget {
  final String baseUrl;
  final String token;

  const EmployeeListScreen({Key? key, required this.baseUrl, required this.token}) : super(key: key);

  @override
  State<EmployeeListScreen> createState() => _EmployeeListScreenState();
}

class _EmployeeListScreenState extends State<EmployeeListScreen> {
  late EmployeeService _service;
  List<EmployeeListItem> _allEmployees = [];
  List<EmployeeListItem> _filteredEmployees = [];
  bool _isLoading = true;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _service = EmployeeService(baseUrl: widget.baseUrl, token: widget.token);
    _loadEmployees();
  }

  Future<void> _loadEmployees() async {
    setState(() => _isLoading = true);
    try {
      final list = await _service.getEmployees();
      setState(() {
        _allEmployees = list;
        _applyFilter();
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  void _applyFilter() {
    if (_searchQuery.isEmpty) {
      _filteredEmployees = _allEmployees;
    } else {
      _filteredEmployees = _allEmployees.where((emp) {
        final query = _searchQuery.toLowerCase();
        return emp.fullName.toLowerCase().contains(query) ||
            (emp.designation?.toLowerCase().contains(query) ?? false) ||
            (emp.department?.toLowerCase().contains(query) ?? false);
      }).toList();
    }
  }

  Future<void> _confirmDeactivate(EmployeeListItem emp) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Deactivate Employee'),
        content: Text('Are you sure you want to deactivate ${emp.fullName}? They will no longer be able to log in.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Deactivate', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _service.deleteEmployee(emp.id, hardDelete: false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Employee deactivated')));
        _loadEmployees();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e'), backgroundColor: Colors.red));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee Directory'),
        backgroundColor: const Color(0xFF1E3A8A),
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          // Search Box
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Search by name, role, department...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
              ),
              onChanged: (val) {
                setState(() {
                  _searchQuery = val;
                  _applyFilter();
                });
              },
            ),
          ),
          // List
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _filteredEmployees.isEmpty
                    ? const Center(child: Text('No employees found'))
                    : RefreshIndicator(
                        onRefresh: _loadEmployees,
                        child: ListView.builder(
                          itemCount: _filteredEmployees.length,
                          itemBuilder: (ctx, idx) {
                            final emp = _filteredEmployees[idx];
                            final isActive = emp.status.toLowerCase() == 'active';
                            return Card(
                              margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              elevation: 2,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                              child: ListTile(
                                leading: CircleAvatar(
                                  backgroundColor: isActive ? const Color(0xFF1E3A8A) : Colors.grey,
                                  child: Text(
                                    emp.fullName.isNotEmpty ? emp.fullName[0].toUpperCase() : 'E',
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                                  ),
                                ),
                                title: Text(emp.fullName, style: const TextStyle(fontWeight: FontWeight.bold)),
                                subtitle: Text('${emp.designation ?? "No Designation"} • ${emp.department ?? "General"}'),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Chip(
                                      label: Text(emp.status.toUpperCase(), style: const TextStyle(fontSize: 10, color: Colors.white)),
                                      backgroundColor: isActive ? Colors.green : Colors.grey,
                                      padding: EdgeInsets.zero,
                                    ),
                                    PopupMenuButton<String>(
                                      onSelected: (action) {
                                        if (action == 'edit') {
                                          Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => EditEmployeeScreen(
                                                employeeId: emp.id,
                                                baseUrl: widget.baseUrl,
                                                token: widget.token,
                                              ),
                                            ),
                                          ).then((_) => _loadEmployees());
                                        } else if (action == 'deactivate') {
                                          _confirmDeactivate(emp);
                                        }
                                      },
                                      itemBuilder: (_) => [
                                        const PopupMenuItem(value: 'edit', child: Text('Edit Profile')),
                                        const PopupMenuItem(value: 'deactivate', child: Text('Deactivate', style: TextStyle(color: Colors.red))),
                                      ],
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => EditEmployeeScreen(
                                        employeeId: emp.id,
                                        baseUrl: widget.baseUrl,
                                        token: widget.token,
                                      ),
                                    ),
                                  ).then((_) => _loadEmployees());
                                },
                              ),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: const Color(0xFF1E3A8A),
        icon: const Icon(Icons.person_add, color: Colors.white),
        label: const Text('Add Employee', style: TextStyle(color: Colors.white)),
        onPressed: () async {
          final result = await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => AddEmployeeScreen(baseUrl: widget.baseUrl, token: widget.token),
            ),
          );
          if (result == true) _loadEmployees();
        },
      ),
    );
  }
}
```

---

### Screen 2: Add Employee Screen (`lib/screens/admin/add_employee_screen.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../services/employee_service.dart';

class AddEmployeeScreen extends StatefulWidget {
  final String baseUrl;
  final String token;

  const AddEmployeeScreen({Key? key, required this.baseUrl, required this.token}) : super(key: key);

  @override
  State<AddEmployeeScreen> createState() => _AddEmployeeScreenState();
}

class _AddEmployeeScreenState extends State<AddEmployeeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _designationCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController(text: "DefaultPassword123!");

  DateTime _joiningDate = DateTime.now();
  int? _departmentId;
  int? _locationId;
  String _role = 'employee';

  List<Map<String, dynamic>> _departments = [];
  List<Map<String, dynamic>> _locations = [];
  bool _isLoading = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _loadOptions();
  }

  Future<void> _loadOptions() async {
    try {
      final s = EmployeeService(baseUrl: widget.baseUrl, token: widget.token);
      final depts = await s.getDepartments();
      final locs = await s.getOfficeLocations();
      setState(() {
        _departments = depts;
        _locations = locs;
        if (depts.isNotEmpty) _departmentId = depts.first['id'];
        if (locs.isNotEmpty) _locationId = locs.first['id'];
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSubmitting = true);

    try {
      final s = EmployeeService(baseUrl: widget.baseUrl, token: widget.token);
      final created = await s.createEmployee({
        "full_name": _nameCtrl.text.trim(),
        "email": _emailCtrl.text.trim().toLowerCase(),
        "phone": _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        "department_id": _departmentId,
        "designation": _designationCtrl.text.trim().isEmpty ? null : _designationCtrl.text.trim(),
        "date_of_joining": DateFormat('yyyy-MM-dd').format(_joiningDate),
        "office_location_id": _locationId,
        "role": _role,
        "password": _passwordCtrl.text.trim(),
      });

      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Employee Created 🎉'),
            content: Text('Name: ${created.fullName}\nCode: ${created.employeeCode}\nEmail: ${created.email}'),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  Navigator.pop(context, true);
                },
                child: const Text('Done'),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add Employee'),
        backgroundColor: const Color(0xFF1E3A8A),
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
                    TextFormField(
                      controller: _nameCtrl,
                      decoration: const InputDecoration(labelText: 'Full Name *', border: OutlineInputBorder()),
                      validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _emailCtrl,
                      decoration: const InputDecoration(labelText: 'Work Email *', border: OutlineInputBorder()),
                      validator: (v) => v == null || !v.contains('@') ? 'Valid email required' : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _phoneCtrl,
                      decoration: const InputDecoration(labelText: 'Phone Number', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<int>(
                      value: _departmentId,
                      decoration: const InputDecoration(labelText: 'Department', border: OutlineInputBorder()),
                      items: _departments.map((d) => DropdownMenuItem<int>(value: d['id'], child: Text(d['name']))).toList(),
                      onChanged: (v) => setState(() => _departmentId = v),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _designationCtrl,
                      decoration: const InputDecoration(labelText: 'Designation', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<int>(
                      value: _locationId,
                      decoration: const InputDecoration(labelText: 'Office Location', border: OutlineInputBorder()),
                      items: _locations.map((l) => DropdownMenuItem<int>(value: l['id'], child: Text(l['name']))).toList(),
                      onChanged: (v) => setState(() => _locationId = v),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      value: _role,
                      decoration: const InputDecoration(labelText: 'Access Role', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'employee', child: Text('Employee')),
                        DropdownMenuItem(value: 'manager', child: Text('Manager')),
                        DropdownMenuItem(value: 'hr_admin', child: Text('HR Administrator')),
                        DropdownMenuItem(value: 'super_admin', child: Text('Super Admin')),
                      ],
                      onChanged: (v) => setState(() => _role = v ?? 'employee'),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _passwordCtrl,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Initial Password', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1E3A8A)),
                        onPressed: _isSubmitting ? null : _submit,
                        child: _isSubmitting
                            ? const CircularProgressIndicator(color: Colors.white)
                            : const Text('Create Employee', style: TextStyle(color: Colors.white, fontSize: 16)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
```

---

### Screen 3: Edit Employee Screen (`lib/screens/admin/edit_employee_screen.dart`)

```dart
import 'package:flutter/material.dart';
import '../../models/employee.dart';
import '../../services/employee_service.dart';

class EditEmployeeScreen extends StatefulWidget {
  final int employeeId;
  final String baseUrl;
  final String token;

  const EditEmployeeScreen({Key? key, required this.employeeId, required this.baseUrl, required this.token})
      : super(key: key);

  @override
  State<EditEmployeeScreen> createState() => _EditEmployeeScreenState();
}

class _EditEmployeeScreenState extends State<EditEmployeeScreen> {
  final _formKey = GlobalKey<FormState>();
  late EmployeeService _service;
  EmployeeDetail? _employee;
  bool _isLoading = true;
  bool _isSaving = false;

  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _designationCtrl = TextEditingController();
  int? _departmentId;
  int? _locationId;
  String _status = 'active';

  List<Map<String, dynamic>> _departments = [];
  List<Map<String, dynamic>> _locations = [];

  @override
  void initState() {
    super.initState();
    _service = EmployeeService(baseUrl: widget.baseUrl, token: widget.token);
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final emp = await _service.getEmployeeById(widget.employeeId);
      final depts = await _service.getDepartments();
      final locs = await _service.getOfficeLocations();

      setState(() {
        _employee = emp;
        _departments = depts;
        _locations = locs;

        _nameCtrl.text = emp.fullName;
        _phoneCtrl.text = emp.phone ?? '';
        _designationCtrl.text = emp.designation ?? '';
        _departmentId = emp.departmentId;
        _locationId = emp.officeLocationId;
        _status = emp.status ?? 'active';

        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);

    try {
      await _service.updateEmployee(widget.employeeId, {
        "full_name": _nameCtrl.text.trim(),
        "phone": _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        "designation": _designationCtrl.text.trim().isEmpty ? null : _designationCtrl.text.trim(),
        "department_id": _departmentId,
        "office_location_id": _locationId,
        "status": _status,
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Employee updated successfully!')));
        Navigator.pop(context, true);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_employee == null ? 'Edit Employee' : 'Edit ${_employee!.employeeCode}'),
        backgroundColor: const Color(0xFF1E3A8A),
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
                    TextFormField(
                      controller: _nameCtrl,
                      decoration: const InputDecoration(labelText: 'Full Name', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _phoneCtrl,
                      decoration: const InputDecoration(labelText: 'Phone', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _designationCtrl,
                      decoration: const InputDecoration(labelText: 'Designation', border: OutlineInputBorder()),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<int>(
                      value: _departmentId,
                      decoration: const InputDecoration(labelText: 'Department', border: OutlineInputBorder()),
                      items: _departments.map((d) => DropdownMenuItem<int>(value: d['id'], child: Text(d['name']))).toList(),
                      onChanged: (v) => setState(() => _departmentId = v),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<int>(
                      value: _locationId,
                      decoration: const InputDecoration(labelText: 'Office Location', border: OutlineInputBorder()),
                      items: _locations.map((l) => DropdownMenuItem<int>(value: l['id'], child: Text(l['name']))).toList(),
                      onChanged: (v) => setState(() => _locationId = v),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      value: _status,
                      decoration: const InputDecoration(labelText: 'Account Status', border: OutlineInputBorder()),
                      items: const [
                        DropdownMenuItem(value: 'active', child: Text('Active')),
                        DropdownMenuItem(value: 'inactive', child: Text('Inactive (Deactivated)')),
                      ],
                      onChanged: (v) => setState(() => _status = v ?? 'active'),
                    ),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1E3A8A)),
                        onPressed: _isSaving ? null : _save,
                        child: _isSaving
                            ? const CircularProgressIndicator(color: Colors.white)
                            : const Text('Save Changes', style: TextStyle(color: Colors.white, fontSize: 16)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
```

---

## 5. Navigation / Drawer Integration

In your Flutter app's navigation drawer or admin dashboard, show the link only to administrators:

```dart
if (currentUser.role == 'super_admin' || currentUser.role == 'hr_admin') ...[
  const Divider(),
  const Padding(
    padding: EdgeInsets.only(left: 16, top: 8, bottom: 4),
    child: Text('ADMINISTRATION', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey)),
  ),
  ListTile(
    leading: const Icon(Icons.people_alt_outlined, color: Color(0xFF1E3A8A)),
    title: const Text('Manage Employees'),
    trailing: const Icon(Icons.chevron_right),
    onTap: () {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => EmployeeListScreen(
            baseUrl: 'https://hrms-backend-z5vv.onrender.com',
            token: authProvider.token,
          ),
        ),
      );
    },
  ),
]
```
