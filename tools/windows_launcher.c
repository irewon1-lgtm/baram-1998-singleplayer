/* Unicode Windows entry point. Launches only this package's engine, keeps
 * local diagnostics, and retries the other graphics driver only if startup
 * stalls. Never opens or modifies any character save or content file. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <wchar.h>
#include <string.h>

static void write_log(HANDLE f, const wchar_t *line) {
    char text[8192]; DWORD used;
    int n=WideCharToMultiByte(CP_UTF8,0,line,-1,text,sizeof(text)-2,NULL,NULL);
    if(n>0 && f!=INVALID_HANDLE_VALUE) {
        text[n-1]='\r';text[n]='\n';WriteFile(f,text,(DWORD)n+1,&used,NULL);FlushFileBuffers(f);
    }
}
static ULONGLONG file_size(const wchar_t *p) {
    WIN32_FILE_ATTRIBUTE_DATA a;
    if(!GetFileAttributesExW(p,GetFileExInfoStandard,&a))return 0;
    return ((ULONGLONG)a.nFileSizeHigh<<32)|a.nFileSizeLow;
}
static BOOL ready_in_output(const wchar_t *p) {
    HANDLE f=CreateFileW(p,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(f==INVALID_HANDLE_VALUE)return FALSE;
    LARGE_INTEGER size,at;DWORD used=0;char tail[16385];BOOL found=FALSE;
    if(GetFileSizeEx(f,&size)) {
        at.QuadPart=size.QuadPart>16384?size.QuadPart-16384:0;
        if(SetFilePointerEx(f,at,NULL,FILE_BEGIN) && ReadFile(f,tail,16384,&used,NULL)) {
            tail[used]=0;found=strstr(tail,"BARAM_GAME_READY")!=NULL;
        }
    }
    CloseHandle(f);return found;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR args,int show) {
    (void)instance;(void)previous;(void)args;(void)show;
    wchar_t root[32768], engine[32768], folder[32768], trace[32768], ready[32768];
    wchar_t output[32768], engine_log[32768], log_path[32768], command[32768], message[32768];
    GetModuleFileNameW(NULL,root,32768);
    wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 2;*slash=0;
    _snwprintf(engine,32768,L"%ls\\engine\\BaramEngine.exe",root);
    _snwprintf(folder,32768,L"%ls\\실행로그",root);
    if(SHCreateDirectoryExW(NULL,folder,NULL)!=ERROR_SUCCESS && GetFileAttributesW(folder)==INVALID_FILE_ATTRIBUTES) {
        wchar_t local[32768];GetEnvironmentVariableW(L"LOCALAPPDATA",local,32768);
        _snwprintf(folder,32768,L"%ls\\BaramSinglePlayer\\logs",local);
        SHCreateDirectoryExW(NULL,folder,NULL);
    }
    SYSTEMTIME now;GetLocalTime(&now);
    wchar_t stamp[128];_snwprintf(stamp,128,L"%04u%02u%02u-%02u%02u%02u-%lu",now.wYear,now.wMonth,now.wDay,now.wHour,now.wMinute,now.wSecond,GetCurrentProcessId());
    _snwprintf(log_path,32768,L"%ls\\%ls-launcher.log",folder,stamp);
    HANDLE log=CreateFileW(log_path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(log==INVALID_HANDLE_VALUE) {
        wchar_t local[32768];
        if(GetEnvironmentVariableW(L"LOCALAPPDATA",local,32768)>0) {
            _snwprintf(folder,32768,L"%ls\\BaramSinglePlayer\\logs",local);
            SHCreateDirectoryExW(NULL,folder,NULL);
            _snwprintf(log_path,32768,L"%ls\\%ls-launcher.log",folder,stamp);
            log=CreateFileW(log_path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
        }
    }
    if(log==INVALID_HANDLE_VALUE) {
        MessageBoxW(NULL,L"실행 기록을 저장할 폴더에 쓸 수 없습니다. ZIP을 다운로드 폴더에 모두 압축 해제한 뒤 다시 실행하세요.",L"바람의나라 실행 오류",MB_OK|MB_ICONERROR);
        return 2;
    }
    write_log(log,L"Baram Windows startup supervisor. Native execution status: user PC run.");
    if(GetFileAttributesW(engine)==INVALID_FILE_ATTRIBUTES) {
        write_log(log,L"ERROR: engine file is missing.");
        MessageBoxW(NULL,L"게임 파일이 없습니다. ZIP 전체를 모두 압축 해제한 뒤 바람의나라.exe를 실행하세요.",L"바람의나라 실행 오류",MB_OK|MB_ICONERROR);
        if(log!=INVALID_HANDLE_VALUE)CloseHandle(log);
        return 2;
    }
    SetEnvironmentVariableW(L"BARAM_PACKAGE_ROOT",root);
    HANDLE job=CreateJobObjectW(NULL,NULL);
    if(job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={0};
        limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits));
    }
    DWORD code=2;BOOL stalled=FALSE;
    for(int attempt=0;attempt<2;attempt++) {
        _snwprintf(trace,32768,L"%ls\\%ls-%d-startup.jsonl",folder,stamp,attempt);
        _snwprintf(ready,32768,L"%ls\\%ls-%d-ready.txt",folder,stamp,attempt);
        _snwprintf(output,32768,L"%ls\\%ls-%d-process.log",folder,stamp,attempt);
        _snwprintf(engine_log,32768,L"%ls\\%ls-%d-engine.log",folder,stamp,attempt);
        SetEnvironmentVariableW(L"BARAM_STARTUP_LOG",trace);
        SetEnvironmentVariableW(L"BARAM_READY_FILE",ready);
        SECURITY_ATTRIBUTES security={sizeof(security),NULL,TRUE};
        HANDLE out=CreateFileW(output,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
        STARTUPINFOW startup={0};startup.cb=sizeof(startup);
        if(out!=INVALID_HANDLE_VALUE) {
            startup.dwFlags=STARTF_USESTDHANDLES;startup.hStdOutput=out;startup.hStdError=out;
            startup.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
        }
        const wchar_t *driver=attempt==0?L"opengl3_angle":L"opengl3";
        _snwprintf(command,32768,L"\"%ls\" --rendering-method gl_compatibility --rendering-driver %ls --log-file \"%ls\"",engine,driver,engine_log);
        write_log(log,attempt==0?L"Attempt 1: ANGLE / Direct3D 11 (native OpenGL fallback if unavailable).":L"Attempt 2: native OpenGL after stalled startup.");
        PROCESS_INFORMATION child={0};
        if(!CreateProcessW(engine,command,NULL,NULL,out!=INVALID_HANDLE_VALUE,CREATE_SUSPENDED,NULL,root,&startup,&child)) {
            _snwprintf(message,32768,L"CreateProcess failed: Windows error %lu",GetLastError());write_log(log,message);
            if(out!=INVALID_HANDLE_VALUE)CloseHandle(out);
            break;
        }
        if(job)AssignProcessToJobObject(job,child.hProcess);
        ResumeThread(child.hThread);CloseHandle(child.hThread);
        if(out!=INVALID_HANDLE_VALUE)CloseHandle(out);
        BOOL playing=FALSE;ULONGLONG size=0;ULONGLONG changed=GetTickCount64();stalled=FALSE;
        while(WaitForSingleObject(child.hProcess,1000)==WAIT_TIMEOUT) {
            if(!playing && (GetFileAttributesW(ready)!=INVALID_FILE_ATTRIBUTES || ready_in_output(output))) {
                playing=TRUE;write_log(log,L"READY: character creation / saved journey is available.");
            }
            ULONGLONG next=file_size(trace)+file_size(output);
            if(next!=size){size=next;changed=GetTickCount64();}
            if(!playing && GetTickCount64()-changed>60000) {
                write_log(log,L"STALLED: no startup progress for 60 seconds. Stopping only this launched engine.");
                TerminateProcess(child.hProcess,3);WaitForSingleObject(child.hProcess,5000);stalled=TRUE;break;
            }
        }
        GetExitCodeProcess(child.hProcess,&code);CloseHandle(child.hProcess);
        _snwprintf(message,32768,L"Engine exit code: %lu",code);write_log(log,message);
        if(!stalled)break;
    }
    if(job)CloseHandle(job);
    if(code!=0) {
        _snwprintf(message,32768,L"게임을 시작하지 못했거나 오류로 종료됐습니다.\n게임 종료 코드: %lu\n\n아래 폴더의 실행 기록을 확인할 수 있습니다.\n%ls\n\n저장 파일을 지우거나 초기화하지 않았습니다.",code,folder);
        MessageBoxW(NULL,message,L"바람의나라 실행 기록",MB_OK|MB_ICONERROR);
        ShellExecuteW(NULL,L"open",folder,NULL,NULL,SW_SHOWNORMAL);
    }
    if(log!=INVALID_HANDLE_VALUE)CloseHandle(log);
    return (int)code;
}
