/* Optional build-host compatibility shim. Some sandbox hosts expose a parent
 * PID namespace at /proc while getpid() returns the child-namespace PID.
 * Redirect ONLY this process's numeric proc path to the kernel's /proc/self.
 * No fabricated process data, game changes, or APK library is involved.
 * Build: cc -shared -fPIC -O2 -Wall -Wextra -Werror proc_self.c -ldl -o proc_self.so
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *self_path(const char *path, char *output) {
    char prefix[64];
    int len = snprintf(prefix, sizeof(prefix), "/proc/%ld", (long)getpid());
    if (path && strncmp(path, prefix, (size_t)len) == 0 && (path[len] == '/' || path[len] == '\0')) {
        int size = snprintf(output, PATH_MAX, "/proc/self%s", path + len);
        if (size > 0 && size < PATH_MAX) return output;
    }
    return path;
}

#define OPEN_WRAPPER(name) \
int name(const char *path, int flags, ...) { \
    static int (*next)(const char *, int, ...); \
    if (!next) next = dlsym(RTLD_NEXT, #name); \
    mode_t mode = 0; \
    if ((flags & O_CREAT) || ((flags & O_TMPFILE) == O_TMPFILE)) { \
        va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); \
    } \
    char output[PATH_MAX]; return next(self_path(path, output), flags, mode); \
}
OPEN_WRAPPER(open)
OPEN_WRAPPER(open64)

#define OPENAT_WRAPPER(name) \
int name(int fd, const char *path, int flags, ...) { \
    static int (*next)(int, const char *, int, ...); \
    if (!next) next = dlsym(RTLD_NEXT, #name); \
    mode_t mode = 0; \
    if ((flags & O_CREAT) || ((flags & O_TMPFILE) == O_TMPFILE)) { \
        va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap); \
    } \
    char output[PATH_MAX]; return next(fd, self_path(path, output), flags, mode); \
}
OPENAT_WRAPPER(openat)
OPENAT_WRAPPER(openat64)

int stat(const char *path, struct stat *value) {
    static int (*next)(const char *, struct stat *); if (!next) next = dlsym(RTLD_NEXT, "stat");
    char output[PATH_MAX]; return next(self_path(path, output), value);
}
int lstat(const char *path, struct stat *value) {
    static int (*next)(const char *, struct stat *); if (!next) next = dlsym(RTLD_NEXT, "lstat");
    char output[PATH_MAX]; return next(self_path(path, output), value);
}
int access(const char *path, int mode) {
    static int (*next)(const char *, int); if (!next) next = dlsym(RTLD_NEXT, "access");
    char output[PATH_MAX]; return next(self_path(path, output), mode);
}
ssize_t readlink(const char *path, char *buf, size_t size) {
    static ssize_t (*next)(const char *, char *, size_t); if (!next) next = dlsym(RTLD_NEXT, "readlink");
    char output[PATH_MAX]; return next(self_path(path, output), buf, size);
}
